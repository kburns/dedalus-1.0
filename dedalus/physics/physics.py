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
from dedalus.data_objects.api import create_data, zero_nyquist, AuxEquation
from dedalus.utils.api import friedmann
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
        self.aux_eqns = {}
    
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

    def _setup_aux_fields(self, t, aux, aux_comp):
         for f, c in zip(aux, aux_comp):
              self.aux_fields[f] = self.create_fields(t, c)

    def _setup_aux_eqns(self, aux_eqns, RHS, ics):
        """ create auxiliary ODEs to be solved alongside the spatial gradients.

        inputs
        ------
        aux_eqns -- a list of names for the equations
        RHS -- 

        """
        for f, r, ic in zip(aux_eqns, RHS, ics):
            self.aux_eqns[f] = AuxEquation(r, ic)

    def RHS(self):
        pass

class Hydro(Physics):
    """incompressible hydrodynamics.

    """
    def __init__(self,*args):
        Physics.__init__(self, *args)
        self.fields = ['ux','uy']
        self._aux_fields = ['vgradv','pressure','gradv']
        aux_types = [None, None, range(4)]
        if self._ndims == 3:
             self.fields.append('uz')
             aux_types[-1] = range(9)
        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        params = {'nu': 0.}

        self.q = self.create_dealias_field(0.,['u','gu','ugu'])
        self._setup_aux_fields(0., self._aux_fields,aux_types)
        self._setup_parameters(params)
        self._RHS = self.create_fields(0.)

    def RHS(self, data):
        """compute right hand side of fluid equations, populating
        self._RHS with the time derivatives of the fields.

        """
        self.vgradv_23dealias(data)
        self.pressure(data)
        vgradv = self.aux_fields['vgradv']
        pressure = self.aux_fields['pressure']
        #insert_ipython()
        for f in self.fields:
            # not sure why this sign is wrong....
            self._RHS[f] = +vgradv[f]['kspace'] - pressure[f]['kspace']
        self._RHS.time = data.time        

        return self._RHS

    def gradv(self, data):
        """compute stress tensor, du_j/dx_i

        """
        gradv = self.aux_fields['gradv']
        i = 0

        for f in self.fields:
            for dim in range(self._ndims):
                gradv[i] = data[f].deriv(self._trans[dim])
                gradv[i]._curr_space = 'kspace'
                zero_nyquist(gradv[i].data)
                i += 1

    def pressure(self, data):
        d = data['ux']
        pressure = self.aux_fields['pressure']
        vgradv = self.aux_fields['vgradv']
        tmp = na.zeros_like(d.data)
        for i,f in enumerate(self.fields):
            tmp +=data[f].k[self._trans[i]] * vgradv[f]['kspace']
        k2 = data['ux'].k2(no_zero=True)

        for i,f in enumerate(self.fields):            
            pressure[f] = data[f].k[self._trans[i]] * tmp/k2
            pressure[f]._curr_space = 'kspace'
            zero_nyquist(pressure[f].data)

    def vgradv(self, data):
        """dealiased vgradv term. This uses temporary dealias fields
        with 3/2 as many points as the shape of the data object.

        """
        d = data['ux']
        self.gradv(data)
        gradv = self.aux_fields['gradv']
        vgradv = self.aux_fields['vgradv']
        trans = {0: 'ux', 1: 'uy', 2: 'uz'}
        self.q.zero_all()
        for i,f in enumerate(self.fields):
            b = [i * self._ndims + j for j in range(self._ndims)]
            tmp = na.zeros_like(self.q['ugu'].data)
            for ii,j, in enumerate(b):
                self.q['u'].data[:]= 0+0j
                self.q['u']._curr_space = 'kspace'
                self.q['gu'].data[:] = 0+0j
                self.q['gu']._curr_space = 'kspace'
                zero_nyquist(data[trans[ii]]['kspace'])
                self.q['u'] = na.fft.fftshift(data[trans[ii]]['kspace'])
                self.q['u'] = na.fft.fftshift(self.q['u']['kspace'])
                self.q['gu'] = na.fft.fftshift(gradv[j]['kspace'])
                self.q['gu'] = na.fft.fftshift(self.q['gu']['kspace'])
                tmp += self.q['u']['xspace'] * self.q['gu']['xspace']
            tmp.imag = 0.
            self.q['ugu'] = tmp
            self.q['ugu']._curr_space = 'xspace'
            vgradv[f] = self.q['ugu']['kspace']
            tmp *= 0+0j

    def vgradv_23dealias(self, data):
        """this computes the vgradv dealiased using 2/3 of the total
        resolution.

        """
        d = data['ux']
        self.gradv(data)
        gradv = self.aux_fields['gradv']
        vgradv = self.aux_fields['vgradv']
        trans = {0: 'ux', 1: 'uy', 2: 'uz'}
        dealias = (na.abs(d.k['x']) > 2/3. *self._shape[0]/2.) | (na.abs(d.k['y']) > 2/3. * self._shape[1]/2.)
        tmp = na.zeros_like(d.data)
        for i,f in enumerate(self.fields):
            b = [i * self._ndims + j for j in range(self._ndims)]
            for ii, j in enumerate(b):
                tmp += data[trans[ii]]['xspace'] * gradv[j]['xspace']
            vgradv[f] = tmp.real
            vgradv[f]._curr_space = 'xspace'
            vgradv[f]['kspace'][dealias] = 0.
            tmp *= 0+0j

    def vgradv_aliased(self, data):
        """fully aliased vgradv term.

        """
        d = data['ux']
        self.gradv(data)
        gradv = self.aux_fields['gradv']
        vgradv = self.aux_fields['vgradv']
        trans = {0: 'ux', 1: 'uy', 2: 'uz'}
        tmp = na.zeros_like(d.data)
        for i,f in enumerate(self.fields):
            b = [i * self._ndims + j for j in range(self._ndims)]
            for ii, j in enumerate(b):
                tmp += data[trans[ii]]['xspace'] * gradv[j]['xspace']
            vgradv[f] = tmp
            vgradv[f]._curr_space = 'xspace'
            tmp *= 0+0j

class LinearCollisionlessCosmology(Physics):
    """This class implements linear, collisionless cosmology. 

    parameters
    ----------
    Omega_r - energy density in radiation
    Omega_m - energy density in matter
    Omega_l - energy density in dark energy (cosmological constant)
    H0      - hubble constant now (100 if all units are in km/s/Mpc)
    solves
    ------
    d_t d = - div(v_)
    d_t v = -grad(Phi) - H v
    laplacian(Phi) = 3 H^2 d / 2

    """
    def __init__(self,*args):
        Physics.__init__(self, *args)
        self.fields = ['delta','ux','uy']
        self._aux_fields = ['gradphi']
        aux_types = [None]
        if self._ndims == 3:
             self.fields.append('uz')
        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        params = {'Omega_r': 0.,
                  'Omega_m': 0.,
                  'Omega_l': 0.,
                  'H0': 100.}
        self._setup_parameters(params)
        self._setup_aux_fields(0., self._aux_fields,aux_types)
        aux_eqn_rhs = lambda a: friedmann(a,self.parameters['H0'],self.parameters['Omega_r'], self.parameters['Omega_m'], self.parameters['Omega_l'])
        
        self._setup_aux_eqns(['H'],[aux_eqn_rhs], [1e-5])

        self._RHS = self.create_fields(0.)

    def RHS(self, data):
        self.density_RHS(data)
        
        return self._RHS

    def density_RHS(self, data):
        pass

    def vel_RHS(self, data):
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']
        for i,f in enumerate(self.fields[1:]):
            self._RHS[f] = -gradphi[f]['kspace'] - self.aux_eqns['H'] * data[f]['kspace']
        
    def grad_phi(self, data):
        gradphi = self.aux_fields['gradphi']
        tmp = -3./2. * self.parameters['H0'] * data['delta']['kspace']/data['delta'].k2(no_zero=True)
        
        for i,f in enumerate(self.fields[1:]):
            gradphi[f] = data[f].k(self._trans(i)) * tmp

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
