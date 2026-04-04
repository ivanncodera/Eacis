from importlib import import_module
import eacis.app as A
M = import_module('eacis.models.user')
print('app.db', id(A.db))
print('model.db', id(M.db))
print('same?', id(A.db) == id(M.db))
