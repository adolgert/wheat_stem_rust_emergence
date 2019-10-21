import xmlrpclib

s = xmlrpclib.ServerProxy('http://128.84.31.84:8000')
print s.next_county(),
