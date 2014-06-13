""" Storage class for sets of pandas object.  Similar to a panel, 
    but does inherently store 3d data.  Data can be converted to 3d through
    methods, but otherwise is just a container."""

from collections import OrderedDict, Iterable
from copy import deepcopy

import logging
from pyuvvis.logger import logclass
from pyuvvis.plotting.multiplots import slice_plot
import pyuvvis.core.utilities as put

logger = logging.getLogger(__name__) 


@logclass(log_name=__name__, public_lvl='debug')
class Stack(object):
    """ Base class to store pandas objects, with special operations to
    return as 3d data (eg panel) and to apply functions itemwise.  Items are
    stored in an ordered dict."""
    
    itemlabel = 'Item'
    
    _magic=['__len__', 
            '__iter__', 
            '__reversed__',
            '__contains__', 
            ]
    
    def __init__(self, data, keys=None, name='', sort_items=False):
        self.name = name
                                
        # Dictionary input
        if isinstance(data, dict):
            logger.debug('Initializing "%s" from dictionary.' % self.full_name)
            if sort_items:
                logger.debug('Sorting keys')
                self._data=OrderedDict(sorted(data.keys(), key=lambda t: t[0]))

            else:
                self._data=OrderedDict(data)

        else:
            
            if not isinstance(data, Iterable):
                logger.info('%s constructed from non-iterable... converting '
                            'data to an iterable' % self.full_name)
                data=[data]
                
            if keys:
                if not isinstance(keys, Iterable):
                    logger.info('%s constructed from non-iterable... converting '
                                'keys to an iterable' % self.full_name)
                    keys = [keys]

                if len(keys) != len(data):
                    raise ValueError('Length mistmatch: keys and data (%s,%s)'\
                        % (len(keys), len(data)))
                
            # If keys not passed, generate them    
            else:
                # Zipped data ((key, df), (key, df))               
                try:
                    keys, data = zip(*data)
                except Exception:                
                    keys=self._gen_keys(len(data))
                    if len(keys) > 1:
                        logger.warn("Generating keys %s-%s" % (keys[0], keys[-1]))
                    else:
                        logger.warn("Generating key %s" % keys[0])

 
            self._data=OrderedDict( [ (keys[i],data[i]) for i 
                                      in range(len(keys) ) ] ) 
        self.__assign_magic()
        
      
    def _gen_keys(self, length):
        """ Return a list of itemlables (item0, item1 etc...) using
            self.itemlabel and a length"""

        logger.debug('Items not found on %s: generating item list' % self.full_name)
        return [self.itemlabel+str(i) for i in range(length)]                  
                
    # --------------------
    # Dictionary Interface  
    def __getitem__(self, keyslice):
        """ If single name, used dict interface.  If slice or integer, uses 
        list interface.  All results parameterized to key, data pairs, passed
        directly into a new Stack.
        """
        # Slice as list of strings or int [0, 'foo', 2, 'bar']
        if hasattr(keyslice, '__iter__'):

            tuples_out = []
            for item in keyslice:
                if isinstance(item, str):
                    item = self._data.keys().index(item)
                tuples_out.append(self._data.items()[item])
                        
        else:
            if isinstance(keyslice, int) or isinstance(keyslice, slice):
                tuples_out = self._data.items()[keyslice] 
            else: 
                tuples_out = [(keyslice, self._data[keyslice])]  #keyslice is name              
        
        # If single item, return TimeSpectra, else, return new Stack
        # Canonical slicing implementaiton; don't change unless good reason
        # Because len() wonky with nested tuples (eg (x,y) and [(x1,y1),(x2,y2)]
        # are both length two, this will work:
        
        if sum(1 for x in tuples_out) == 2:
            return tuples_out[1] #Return timespectra
        else:
            return self.__class__(tuples_out)                


    def __delitem__(self, keyslice):
        """ Delete a single name, or a keyslice from names/canvas """        

        if isinstance(keyslice, str):
            idx = self.names.index(keyslice)        
            self.pop(idx)
        else:
            raise NotImplementedError("Deletion only supports single entry")

    def __setitem__(self, name, canvas):
        """ """
        if name in self.names:
            idx = self.names.index(name) 
            self.pop(idx)
            self.insert(idx, name, canvas)
            
        else:
            self.names.append(name)  
                
    def __getattr__(self, attr):
        """ If attribute not found, try attribute lookup in dictionary.  If
        that is not found, try finding attribute on self._data.
        
        For example, self.keys() will first look for self['keys'].  Since
        this isn't found, it calls self._data.keys().  But if I do 
        self.Item1, then it returns self['Item1'].  The very rare conflict
        case that a user has named the items a method that may already exist
        in the dictionary (eg items=['a','b','keys'] is addressed.
        """
        
        if attr in self._data.keys():
            if hasattr(self._data, attr):
                raise AttributeError('"%s attribute" found in both the items\
                and as a method of the underlying dictionary object.'%(attr))
            else:
                return self[attr]
        return getattr(self._data, attr)
        

    def __assign_magic(self):
        for meth in self._magic:
            setattr( self, meth, getattr(self._data, meth) )

        
        
    def as_3d(self):
        """ Return 3d structure of data.  Default is panel."""
        raise Panel(data=self._data)
                 
        ### Data types without labels    

    
    #Is this realy necessary?  See pyparty.ParticleManger for possibly more consistent implementation
    def get_all(self, attr, astype=tuple):
        """Generator/tuple etc.. of (item, attribute) pairs. """
        
        return put._parse_generator(
            ((item[0], getattr(item[1], attr)) for item in self.items()), astype)
    
                
    def _get_unique(self, attr):
        """ Inspects Stack itemwise for an attribute for unique values.
        If non-unique value for the attributes are found, returns
        "mixed". """
        unique = set(self.get_all(attr, astype=dict).values())
        if len(unique) > 1:
            return 'mixed'
        else:
            return tuple(unique)[0] #set doesn't support indexing         
        
        
    def set_all(self, attr, val, inplace=False):
        """ Set attributes itemwise.  
            If not inplace, returns new instance of self"""
        if inplace:
            for (key, item) in self.items():
                try:           
                    setattr(item, attr, val)    
                except Exception as E:
                    raise Exception('Could not set %s in "%s".  Received the following \
                     exception:\n "%s"'%(attr, key, E))
        else:
            out=deepcopy(self._data) #DEEPCOPY            
            for item in out:
                setattr(out[item], attr, val)                
            return self.__class__(out)


    def apply(self, func, *args, **kwargs):
        """ Applies a user-passed function, or calls an instance method itemwise.
        
        
        Parameters:
        -----------
        func: str or function
            If string, must correspond to a method on the object stored 
            itemwise in the stack.  If a function, appliked itemwise to
            objects stored.  
              
        inplace: False 
            Special kwarg.  If true, self._data modified inplace, 
            otherwise new specstack is returned.
                         
        *args, **kwargs: 
            func arguments.
          
        Returns:
        --------
        If not inplace, returns SpecStack after itemwise application.
            
        """   

        inplace=kwargs.pop('inplace', False)
        
        if isinstance(func, basestring):
            if inplace:
                for item in self:
                    self[item]=getattr(self[item], func)(*args, **kwargs)      

            else:                
                return self.__class__(OrderedDict([(k, getattr(v, func)(*args, \
                                 **kwargs)) for k,v in self.items()]))                
             
        # function, numpyfunction etc...   
        else:
            if inplace:
                for item in self:
                    self[item]=self[item].apply(func)(*args, **kwargs)
                    
            else:
                return self.__class__(OrderedDict([(k, v.apply(func, *args, \
                                 **kwargs)) for k,v in self.items()]))                  
                
        

    @property  
    def full_name(self):
        """ Timespectra:name or Timespectra:unnamed.  Useful for scripts mostly """
        outname = getattr(self, 'name', 'unnamed')
        return '%s:%s' % (self.__class__.__name__, self.name)           
    
    #def __repr__(self):
        #""" """



@logclass(log_name=__name__)               
class SpecStack(Stack):
    """ Stack for just storing timespectra objects."""        

    itemlabel='spec_'

    def as_3d(self, **kwargs):
        """ Returns a 3d stack (SpecPanel) of the currently stored items.
            Additional kwargs can be passed directly to SpecPanel constructor."""
        from specpanel import SpecPanel      
        return SpecPanel(data=self._data, **kwargs)        
    
    
    ### Special properties for swift, in-place attribute overwrites of most 
    ### common itemwise operation.  Getter only tests for uniqueness
    
    @property
    def specunit(self):
        return self._get_unique('specunit')

                
    ### Do I want to make as a _set method to avoid accidental overwrite?
    @specunit.setter
    def specunit(self, unit):
        """ Sets specunit for every stored TimeSpectra."""
        self.set_all('specunit', unit, inplace=True)
    
    @property
    def iunit(self):
        return self._get_unique('iunit')    
    
    @iunit.setter
    def iunit(self, unit):
        """ Sets iunit for every stored TimeSpectra."""
        self.set_all('iunit', unit, inplace=True)    
        
    @property
    def reference(self):
        return self._get_unique('reference')
    
    @reference.setter
    def reference(self, ref):
        """ Set reference itemwise.  No getter, use get_all() instead."""
        self.set_all('reference', ref, inplace=True)

    ### This shouldn't have a setter
    @property
    def timeunit(self):
        return self._get_unique('timeunit')   
    
    def plot(self, *plotargs, **plotkwargs):
        """Returns multiplot of current stack.  
        
        Notes
        -----
        Wraps pyuvvis.plotting.multiplots.slice_plot()
        """
        
        plotkwargs.setdefault('title', self.name)        
        if 'cbar' in plotkwargs:
            raise NotImplementedError("Colorbar on stack plot not yet supported")
        return slice_plot(self.values(), *plotargs, names=self.keys(), **plotkwargs)

        
   

if __name__=='__main__':
    ### For testing.
    from pyuvvis.core.specindex import SpecIndex
    from pyuvvis.core.timespectra import TimeSpectra
    from pandas import date_range, DataFrame, Index

    import numpy as np       
    import matplotlib.pyplot as plt

    spec = SpecIndex(np.arange(400, 700,10), unit='nm' )
    spec2 = SpecIndex(np.arange(400, 700,10), unit='m' )
    
    testdates = date_range(start='3/3/12', periods=30, freq='h')
    testdates2 = date_range(start='3/3/12', periods=30, freq='h')
    
    ts = TimeSpectra(abs(np.random.randn(30,30)), columns=testdates, index=spec)  
    t2 = TimeSpectra(abs(np.random.randn(30,30)), columns=testdates2, index=spec2) 
    d = (('d1', ts), ('d2', t2))

    ##x = Panel(d)
    y = SpecStack(d, name='Slices of Foo')
    y.reference = 0
    y.iunit='a'
    y.plot()
    plt.show()
#    sys.exit()
    #y[0:1]
    #y['d1',1]
    #x = y.set_all('specunit', 'cm')
    #y._get_unique('specunit')
    #y.apply('wavelength_slices', 8)
    #y['d1']
    
    x=y.apply(np.sqrt, axis=1)
    print 'hi'
    #y.applynew('boxcar', binwidth=10)
    #y.applynew(boxcar, binwidth=10)
    ##print y.specunit
    ##y.specunit='f'
    #print 'hi'