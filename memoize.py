'''
memoized is a decorator for functions that remembers what the
return value was given a particular set of arguments. If it is
called again with the same arguments, it will get the same 
return value.

@memoized
def get_data():
    # read file
    # get bounding boxes of US States.

This code is copied from the Python wiki.
'''
import functools

class memoized(object):
    def __init__(self,func):
        self.func=func
        self.cache={}
    def __call__(self,*args,**kwargs):
        try:
            return self.cache[args]
        except KeyError:
            value=self.func(*args)
            self.cache[args]=value
            return value
        except TypeError:
            return self.func(*args)
    def __repr__(self):
        return self.func.__doc__
    def __get__(self,obj,objtype):
        return functools.partial(self.__call__,obj)
