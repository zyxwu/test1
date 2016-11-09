# -*- coding: utf-8 -*-

from sqlalchemy.dialects.postgresql import JSONB  # Integer, ForeignKey, String, Column, create_engine
from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import relationship, sessionmaker, JSON
from werkzeug.security import generate_password_hash
from random import randint, sample
import string
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import hashlib


DEFAULT_DOCS_PER_PAGE = 50                                  # количество выводимых документов на экран
DEFAULT_FIELDS = ['tags', 'comments']                   # и поля документа для вывода (по-умолчанию)
DEFAULT_MAX_COLUMN_WIDTH = 50

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:@localhost/testing'
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

current_user = 'sa'         ##############################################################################
current_page_settings = 'General email'


db = SQLAlchemy(app)            # represents the DB and provides access to all functionality  of Flask-SQLAlchemy
# print dir(db.session)

# engine = create_engine('postgresql://postgres:@localhost/testing')
# Base = declarative_base()         # Base class from which all mapped classes should inherit
# Session = sessionmaker(engine)    # Defines a class (Session), which will serve as a factory for new Session objects
# session = Session()               # Instantiates a Session to start talking to DB


class PageSettings(db.Model):
    """ Maintains document view settings for each user:

            `docs_per_page` - count of documents per page,
            `max_column_width` - column width in a tabled view,
            `indices` - related to the view,
            `fields` - index's fields (columns) to display
            `user_id` - user's (owner) ID from `Users` table
    """
    __tablename__ = 'page_settings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    _user_id = db.Column('user_id', db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(64), unique=True, index=True)
    _rest = db.Column('rest', JSONB)         # This includes: `docs_per_page`, `max_column_width` and others

    def __init__(self, name, **kwargs):
        self._user_id = User.query.filter_by(name=current_user).first().id
        self.name = name
        self._rest = {}
        self._rest['fields'] = []
        self._rest['indices'] = []
        for key, value in kwargs.iteritems():
            self._rest[key] = value

    saved_queries = db.relationship('SavedQuery', backref='page_settings')

    @property
    def user_id(self):
        return User.query.filter_by(id=self._user_id).first().name

    @property
    def rest(self):
        return self._rest

    @rest.setter
    def rest(self, value):
        if isinstance(value, dict):
            self._rest.update(value)
        # else:
        #     # TODO: добавить логгер
        #     raise AttributeError('Unknown')

    def __repr__(self):
        return "<PageSettings(name='%s', owner='%s', indices='%s', fields='%s', rest='%s')>" %\
               (self.name, self.user_id, self.rest['indices'], self.rest['fields'],
                filter(lambda x: x[0] != 'indices' and x[0] != 'fields', self.rest.iteritems()))


class SavedQuery(db.Model):
    """ Maintains saved index queries:

            `index` - index to query,
            `doc_type` - doc_type expression to query (maybe value, enumeration, RE),
            `user_id` - user's (owner) ID from `users` table
            `page_settings` - view settings ID from `page_settings` table
            `request_body` - query DSL
    """
    __tablename__ = 'queries'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, index=True)
    _user_id = db.Column('user_id', db.Integer, db.ForeignKey('users.id'))
    _page_settings_id = db.Column('page_settings_id', db.Integer, db.ForeignKey('page_settings.id'))
    index = db.Column(db.String(64))
    doc_type = db.Column(db.String(255))
    request_body = db.Column('query', JSONB)

    def __init__(self, name, index, query, doc_type=''):
        self.name = name
        self.index = index
        self.doc_type = doc_type
        self._user_id = User.query.filter_by(name=current_user).first().id
        self._page_settings_id = PageSettings.query.filter_by(name=current_page_settings).first().id
        self.request_body = query

    @property
    def user_id(self):
        return User.query.filter_by(id=self._user_id).first().name

    @property
    def page_settings_id(self):
        return PageSettings.query.filter_by(id=self._page_settings_id).first().name

    @property
    def request_head(self):
        return 'GET ' + self.index + ('/' + self.doc_type + '/' if self.doc_type else '/') + '_search<br>'

    @property
    def request_id(self):
        return hashlib.md5(self.request_head + str(self.request_body)).hexdigest()

    def __repr__(self):
        return "<SavedQuery(name='%s', owner='%s', page_settings='%s', head='%s', body='%s', id='%s')>" %\
               (self.name, self.user_id, self.page_settings_id,
                self.request_head, self.request_body,
                self.request_id)


class Role(db.Model):                              # Base == db.Model
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)   # db.Column == Column
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.String(255))
    # Option `lazy` specifies how the ralated items are to be loaded
    users = db.relationship('User', backref='role', lazy='dynamic')

    def __repr__(self):
        return self.name


class User(db.Model):
    __tablename__ = 'users'

    def __init__(self, role_id=None, **kwargs):
        self.role_id = role_id or db.session.query(Role).filter_by(name='user').first().id
        for key, value in kwargs.iteritems():
            if key == 'role_id':
                continue
            else:
                self.__setattr__(key, value)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    page_settings = db.relationship('PageSettings', backref='users')    # , lazy='dynamic')
    saved_queries = db.relationship('SavedQuery', backref='queries')    # , lazy='dynamic')

    @property
    def password(self):
        raise AttributeError('Password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def __repr__(self):
        return "<User(name='%s', email='%s', password_hash='%s', role='%s')>" %\
               (self.name, self.email, self.password_hash, db.session.query(Role).filter_by(id=self.role_id).first())

#
# # Base.metadata.create_all(engine)
# # session.add_all([Role(name='admin'), Role(name='user')])
# # session.commit()
# # rand_users = {''.join(sample(string.ascii_lowercase, 5)).title(): ''.join(sample(string.digits, i)) for i in xrange(10)}
# # session.add_all(map(lambda x: User(name=x[0], password=x[1], email=x[0]+'@test.net'), rand_users.iteritems()))
# # session.commit()
#
# query = session.query(User).filter(User.name.like('%z%')).order_by(User.id)
# # print query.all()
# # test_user = User(name='ed', password='test')

# db.session.add_all(map(lambda x: User(name='Admin' + str(x),
#                                       password='Admin' + str(x),
#                                       role_id=1, email='Admin' + str(x) + '@test.net'),
#                        xrange(2)))
# db.session.commit()
# for u, r in db.session.query(User, Role).filter(User.role_id == Role.id).filter(User.name.like('%d%')).all():
#     print u, r

# user_role = Role.query.filter_by(name='user').first()
# admin_role = Role.query.filter_by(name='Administrator').first()
# moderator_role = Role.query.filter_by(name='moderator').first()
# print moderator_role.id
# for user in User.query.filter_by(role_id=user_role).all():
#     print user.name, user.role_id


# # print User.__mapper__
# # print User.__tablename__
# print os.path.abspath(os.curdir)


# ps = PageSettings('General email', docs_per_page=10, max_column_width=50,
#                   fields=DEFAULT_FIELDS, indices=['email', 'mbox'])
#
# db.session.add(ps)
# db.session.commit()

# print 'Admins are: ' + str(map(lambda x: str(x.name), Role.query.filter_by(name='Administrator').first().users))
# print 'Users are:  ' + str(map(lambda x: str(x.name), Role.query.filter_by(name='user').first().users))
# print
# for user, role in db.session.query(User, Role).filter(User.role_id == Role.id).filter(User.name.like('%d%')).\
#         order_by(User.name).all():
#     print user.name, role.name

# moderator = Role(name='moderator')
# db.session.add(moderator)
# db.session.commit()

# md = User(name='ed', password='ed', role_id=moderator_role.id)
# print md

# administrator = Role.query.filter_by(name='admin').first()
# administrator.name = 'Administrator'
# db.session.commit()

# Role.query.filter_by(name='Administrator').first().users))
# ea = Role.query.filter_by(name='Administrator').first().users
# # print ea
# # print type(ea), dir(ea)
# print ea.count()
# print user_role.users.count()
# print user_role.users.count()     # [0].users.all().count()

# a = User.query.filter_by(role=admin_role).first()
# a = User.query.filter_by(name='ed').first().id

# User.query.filter_by(name=current_user).first().id or
# su = Role(name='SuperAdmin', description='Superuser to handle non-standard situation')
# db.session.add(su)
# db.session.add(User(name='sa', role=su))
# db.session.commit()

print '---------------------------------'

db.create_all()

sq = SavedQuery('first', 'email', {
        "sort": [],
        "query": {
                "bool": {
                        "filter": [],
                        "should": [],
                        "must_not": [],
                        "must": [
                                {
                                        "match": {
                                                "_all": "958879878"
                                        }
                                }
                        ]
                }
        },
        "version": "true",
        "_source": {
                "exclude": [
                        "*._content"
                ],
                "include": [
                        "_version",
                        "ab_a",
                        "ab_b",
                        "c_type",
                        "dt",
                        "tm",
                        "dur",
                        "info",
                        "tags",
                        "comments"
                ]
        }
})


print User.query.filter_by(name=current_user).first().name
# print current_page_settings
print PageSettings.query.filter_by(name=current_page_settings).first().name
print sq
# ps = PageSettings(name=current_page_settings)
# ps.rest['fields'] = DEFAULT_FIELDS
# ps.rest['indices'] = 'email'
# ps.rest['docs_per_page'] = DEFAULT_DOCS_PER_PAGE
# ps.rest['max_column_width'] = DEFAULT_MAX_COLUMN_WIDTH


print '============='
