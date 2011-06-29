"""Physics class. This defines fields, and provides a right hand side
to time integrators.

Author: J. S. Oishi <jsoishi@gmail.com>
Affiliation: KIPAC/SLAC/Stanford
License:
  Copyright (C) 2011 J. S. Oishi.  All Rights Reserved.

  This file is part of dedalus.

  dedalus is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as na
from dedalus.data_objects.api import create_data, zero_nyquist

from dedalus.funcs import insert_ipython
class Physics(object):
    """This is a base class for a physics object. It needs to provide
    a right hand side for a time integration scheme.
    """
    def __init__(self, shape, representation):
        self._shape = shape
        self._ndims = len(self._shape)
        self._representation = representation
        dataname = "%sData" % self.__class__.__name__
        self.__DataClass = create_data(self._representation, self._shape, dataname)
        self.parameters = {}
        self.fields = {}
        self.aux_fields = {}
    
    def __getitem__(self, item):
         a = self.parameters.get(item, None)
         # if a is None:
         #      a = self.parameters.get(item, None)
         if a is None:
              raise KeyError
         return

    def create_fields(self, t, fields=None):
         if fields == None:
              return self.__DataClass(self.fields, t)
         else:
              return self.__DataClass(fields, t)

    def create_dealias_field(self, t, fields=None):
        """data object to implement Orszag 3/2 rule for non-linear
        terms.

        """
        name = "%sDealiasData" % self.__class__.__name__
        shape = [3*d/2 for d in self._shape]
        data_class = create_data(self._representation, shape, name)

        if fields == None:
            return data_class(self.fields, t)
        else:
            return data_class(fields, t)

    def _setup_parameters(self, params):
        for k,v in params.iteritems():
            self.parameters[k] = v

    def _setup_aux_fields(self, aux):
         for f in aux:
              self.aux_fields[f] = representation(self,shape)

    def RHS(self):
        pass

class Hydro(Physics):
    """incompressible hydrodynamics.

    """
    def __init__(self,*args):
        Physics.__init__(self, *args)
        self.fields = ['ux','uy']
        self._naux = 4
        if self._ndims == 3:
             self.fields.append('uz')
             self._naux = 9
        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        params = {'nu': 0.}
        
        self.aux_fields = []
        # for i in range(self._naux):
        #      self.aux_fields.append(self._representation(self._shape))
        self._setup_parameters(params)
        self._RHS = self.create_fields(0.)

    def RHS(self, data):
        vgradv = self.vgradv(data)
        pressure = self.pressure(data, vgradv)
        for f in self.fields:
            self._RHS[f] = -vgradv[f]['kspace'] + pressure[f]['kspace']
            #self._RHS[f]['kspace'].ravel()[0] = 0.
        self._RHS.time = data.time        

        return self._RHS

    def gradv(self, data):
        """compute stress tensor, du_j/dx_i

        """
        gradv = self.create_fields(data.time,fields=range(self._ndims**2))
        i = 0

        slices = self._ndims*(slice(None),)
        for f in self.fields:
            for dim in range(self._ndims):
                gradv[i] = data[f].deriv(self._trans[dim])
                zero_nyquist(gradv[i].data)
                i += 1
                
        return gradv

    def pressure(self, data, vgradv):
        d = data['ux']
        pressure = self.create_fields(data.time)
        tmp = na.zeros_like(d.data)
        for i,f in enumerate(self.fields):
            tmp +=data[f].k[self._trans[i]] * vgradv[f]['kspace']
        k2 = data['ux'].k2(no_zero=True)

        for i,f in enumerate(self.fields):            
            pressure[f] = data[f].k[self._trans[i]] * tmp/k2
            zero_nyquist(pressure[f].data)

        return pressure

    def vgradv(self, data):
        """dealiased vgradv term

        """
        d = data['ux']
        gradv = self.gradv(data)
        vgradv = self.create_fields(data.time)
        trans = {0: 'ux', 1: 'uy', 2: 'uz'}

        q = self.create_dealias_field(data.time,['u','gu','ugu'])
        for i,f in enumerate(self.fields):
            b = [i * self._ndims + j for j in range(self._ndims)]
            tmp = na.zeros_like(q['ugu'].data)
            for ii,j, in enumerate(b):
                q['u'].data[:]= 0+0j
                q['u']._curr_space = 'kspace'
                q['gu'].data[:] = 0+0j
                q['gu']._curr_space = 'kspace'
                zero_nyquist(data[trans[ii]]['kspace'])
                q['u'] = na.fft.fftshift(data[trans[ii]]['kspace'])
                q['u'] = na.fft.fftshift(q['u']['kspace'])
                q['gu'] = na.fft.fftshift(gradv[j]['kspace'])
                q['gu'] = na.fft.fftshift(q['gu']['kspace'])
                tmp += q['u']['xspace'] * q['gu']['xspace']
            tmp.imag = 0.
            q['ugu'] = tmp
            q['ugu']._curr_space = 'xspace'
            vgradv[f] = q['ugu']['kspace']
            tmp *= 0+0j

        return vgradv

    def vgradv_aliased(self, data):
        """fully aliased vgradv term.

        """
        d = data['ux']
        gradv = self.gradv(data)
        vgradv = self.create_fields(data.time)
        trans = {0: 'ux', 1: 'uy', 2: 'uz'}
        for i,f in enumerate(self.fields):
            b = [i * self._ndims + j for j in range(self._ndims)]
            tmp = na.zeros_like(d.data)
            for ii, j in enumerate(b):
                tmp += data[trans[i]]['xspace'] * gradv[j]['xspace']
            vgradv[f] = tmp
            tmp *= 0+0j

        return vgradv


if __name__ == "__main__":
    import pylab as P
    from fourier_data import FourierData
    from init_cond import taylor_green
    a = Hydro((100,100),FourierData)
    data = a.create_fields(0.)
    taylor_green(data['ux'],data['uy'])
    vgv = a.vgradv(data)
    #test = a.pressure(data,vgv)
    test = a.RHS(data)

    for i,f in enumerate(a.fields):
        print test[f]._curr_space
        P.subplot(1,2,i+1)
        P.imshow(test[f]['xspace'].real)
        tmp =test[f]['xspace'].imag
        print "%s (min, max) = (%10.5e, %10.5e)" % (f, tmp.min(), tmp.max())
        P.colorbar()

    P.show()
