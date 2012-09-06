"""
Physics classes. These defines fields, and provides a right hand side
to time integrators.

Authors: J. S. Oishi <jsoishi@gmail.com>
         K. J. Burns <kburns@berkeley.edu>
Affiliation: KIPAC/SLAC/Stanford
License:
  Copyright (C) 2011 J. S. Oishi, K. J. Burns.  All Rights Reserved.

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
from dedalus.data_objects.representations import FourierRepresentation, \
        FourierShearRepresentation
from dedalus.utils.logger import mylog
from dedalus.data_objects.api import create_field_classes, AuxEquation, StateData
from dedalus.utils.api import a_friedmann
from dedalus.funcs import insert_ipython

def _reconstruct_object(*args, **kwargs):
    new_args = [args[1]['shape'], args[1]['_representation'], args[1]['length']]
    obj = args[0](*new_args)
    obj.__dict__.update(args[1])
    return obj

class Physics(object):
    """
    Base class for a physics object. Defines fields and provides
    a right hand side for the time integration scheme.

    """

    allowable_representations = []

    def __init__(self, shape, representation, length=None):
        """
        Base class for a physics object. Defines fields and provides
        a right hand side for the time integration scheme.

        Parameters
        ----------
        shape : tuple of ints
            The shape of the data in xspace: (z, y, x) or (y, x)
        representation : class
            A Dedalus representation class
        length : tuple of floats, optional
            The length of the data in xspace: (z, y, x) or (y, x),
            defaults to 2 pi in all directions.

        """

        # Store inputs
        self.shape = shape
        if representation in self.__class__.allowable_representations:
            self._representation = representation
        else:
            raise ValueError("Specified representation is incompatible with this physics class.")
        if length:
            self.length = length
        else:
            self.length = (2 * na.pi,) * len(self.shape)

        # Dimensionality
        self.ndim = len(self.shape)
        self.dims = xrange(self.ndim)

        # Additional setup
        self._field_classes = create_field_classes(
                self._representation, self.shape, self.length)
        self.aux_eqns = {}

        self._is_finalized = False

    def __getitem__(self, item):
         value = self.parameters.get(item, None)
         if value is None:
              raise KeyError
         return value

    def __reduce__(self):
        savedict = {}
        exclude = ['aux_fields', '_field_classes']
        for k,v in self.__dict__.iteritems():
            if k not in exclude:
                savedict[k] = v
        return (_reconstruct_object, (self.__class__, savedict))

    def _finalize(self):
        self._setup_aux_fields(0., self._aux_fields)
        self._is_finalized = True

    def create_fields(self, time, field_list=None):
        if field_list == None:
            field_list = self.fields

        return StateData(time, self.shape, self.length, self._field_classes,
                         field_list=field_list, params=self.parameters)

    def _setup_aux_fields(self, t, aux_field_list=None):
        self.aux_fields = self.create_fields(t, aux_field_list)

    def _setup_aux_eqns(self, aux_eqns, RHS, ics, kwarglists):
        """ create auxiliary ODEs to be solved alongside the spatial gradients.

        inputs
        ------
        aux_eqns -- a list of names for the equations
        RHS --

        """
        for f, r, ic, kwargs in zip(aux_eqns, RHS, ics, kwarglists):
            self.aux_eqns[f] = AuxEquation(r, kwargs, ic)

    def RHS(self, data, deriv):
        # Finalize and setup integrating factors
        if not self._is_finalized:
            self._finalize()
            self._setup_integrating_factors(deriv)

        for name,f in deriv:
            f.zero_all()
        deriv.set_time(data.time)
        self.aux_fields.set_time(data.time)

    def gradX(self, X, output):
        """
        Compute Jacobian: gradX[N * i + j] = dX_i/dx_j

        Parameters
        ----------
        X : Scalar/VectorField object
            Input field
        output : Vector/TensorField object
            Field for storing output

        """

        N = self.ndim

        # Construct Jacobian
        for i in xrange(X.ncomp):
            for j in self.dims:
                output[N * i + j]['kspace'] = X[i].deriv(self._trans[j])

    def divX(self, X, output):
        """
        Compute divergence: divX = dX_i/dx_i

        Inputs:
            X           Input VectorField object
            output      Output ScalarField object

        """

        N = self.ndim
        output.zero()

        # Construct divergence
        for i in xrange(X.ncomp):
            output['kspace'] += X[i].deriv(self._trans[i])

    def XgradY(self, X, Y, gradY, output, compute_gradY=True):
        """
        Calculate X dot (grad Y).

        Inputs:
            X           Input VectorField object
            Y           Input Scalar/VectorField object
            gradY       Vector/TensorField object to hold gradY
            output      Output Scalar/VectorField object

        Keywords:
            compute_gradY   Set to False if gradY has been computed

        """

        N = self.ndim

        # Perform gradY calculation
        if compute_gradY:
            self.gradX(Y, gradY)

        # Setup temporary data container
        sampledata = output[0]
        output.zero_all()
        tmp = na.zeros_like(sampledata['xspace'])

        # Construct XgradY
        for i in xrange(Y.ncomp):
            for j in self.dims:
                tmp += X[j]['xspace'] * gradY[N * i + j]['xspace']
            output[i]['xspace'] += tmp.real
            tmp *= 0+0j

    def XlistgradY(self, Xlist, Y, stmp, vtmp, outlist):
        """
        Calculate X dot (grad Y) for X in Xlist.
        This is a low-memory alternative to XgradY (never stores a full gradY tensor).

        Inputs:
            Xlist       List of input VectorField objects
            Y           Input Scalar/VectorField object
            stmp        List of ScalarField object for use in internal calculations
            vtmp        VectorField object for use in internal calculations
            outlist     List of output Scalar/VectorField object

        """

        N = self.ndim

        # Zero all output fields
        for outfield in outlist:
            outfield.zero_all('xspace')

        for i,X in enumerate(Xlist):
            for j in xrange(X.ncomp):
                vtmp[i][j]['kspace'] = X[j]['kspace']
                vtmp[i][j]['xspace']

        for i in xrange(Y.ncomp):
            for j in self.dims:
                # Compute dY_i/dx_j
                stmp['kspace'] = Y[i].deriv(self._trans[j])

                # Add term to each output
                for k,X in enumerate(vtmp):
                    #outlist[k][i]['xspace'] += (X[j]['xspace'] * stmp['xspace']).real
                    na.add(outlist[k][i]['xspace'], (X[j]['xspace'] * stmp['xspace']), outlist[k][i]['xspace'])

    def XcrossY(self, X, Y, output, space):
        """
        Calculate X cross Y.

        Inputs:
            X           Input VectorField object
            Y           Input VectorField object
            output      Output Vector/ScalarField object (3D/2D)
            space       Space for cross product

        Note:
            2D inputs require scalar output
            3D inputs require vector output

        """

        N = X.ndim

        # Place references
        X0 = X[0][space]
        X1 = X[1][space]
        if N == 3: X2 = X[2][space]

        Y0 = Y[0][space]
        Y1 = Y[1][space]
        if N == 3: Y2 = Y[2][space]

        # Calculate cross product, scalar if N == 2
        if N == 3:
            output[0][space] = X1 * Y2 - X2 * Y1
            output[1][space] = X2 * Y0 - X0 * Y2
            output[2][space] = X0 * Y1 - X1 * Y0
        else:
            output[space] = X0 * Y1 - X1 * Y0

    def XdotY(self, X, Y, output, space):
        """
        Calculate X dot Y.

        Inputs:
            X           Input VectorField object
            Y           Input VectorField object
            output      Output ScalarField object
            space       Space for dot product

        """

        if X.ncomp != Y.ncomp: raise ValueError('Vectors not the same size')

        output.zero()
        for i in xrange(X.ncomp):
            output[space] += X[i][space] * Y[i][space]

    def curlX(self, X, output):
        """
        Calculate curl of X.

        Inputs:
            X           Input Scalar/Vector/VectorField object
            output      Output Vector/Scalar/VectorField object (2D/2D/3D)

        Note:
            2D: Vector input requires Scalar output
                Scalar input requires Vector output
            3D: Vector input requires Vector output

        """

        N = X.ncomp

        # Calculate curl
        # 3D input yields 3D output
        if N == 3:
            output[0]['kspace'] = X[2].deriv(self._trans[1]) - X[1].deriv(self._trans[2])
            output[1]['kspace'] = X[0].deriv(self._trans[2]) - X[2].deriv(self._trans[0])
            output[2]['kspace'] = X[1].deriv(self._trans[0]) - X[0].deriv(self._trans[1])

        # 2D input (xy) yields scalar output (z)
        elif N == 2:
            output['kspace'] = X[1].deriv(self._trans[0]) - X[0].deriv(self._trans[1])

        # Scalar input (z) yeilds vector output (xy)
        elif N == 1:
            output[0]['kspace'] = X[0].deriv(self._trans[1])
            output[1]['kspace'] = -X[0].deriv(self._trans[0])

class IncompressibleHydro(Physics):
    """
    Incompressible hydrodynamics.

    Parameters *** Set in self.parameters dictionary after instantiation. ***
    ----------
    'viscosity_order' : int
        Hyperviscosity order. Defaults to 1.
    'nu' : int
        Kinematic viscosity. Defaults to 0.
    'rho0' : float
        Background density. Defaults to 1.

    Example
    -------
    >>> physics = IncompressibleHydro((128, 128), FourierRepresentation)
    >>> physics.parameters['viscosity_order'] = 2

    """

    allowable_representations = [FourierRepresentation]

    def __init__(self, *args, **kwargs):
        Physics.__init__(self, *args, **kwargs)

        # Setup data fields
        self.fields = [('u', 'VectorField')]
        self._aux_fields = [('pressure', 'VectorField'),
                            ('mathtmp', 'ScalarField'),
                            ('ucopy','VectorField'),
                            ('ugradu', 'VectorField')]

        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        self.parameters = {'rho0': 1.,
                           'viscosity_order': 1,
                           'nu': 0.}

    def _setup_integrating_factors(self, deriv):

        # Kinematic viscosity for u
        for cindex, comp in deriv['u']:
            nu = self.parameters['nu']
            vo = self.parameters['viscosity_order']
            if nu == 0.:
                comp.integrating_factor = None
            else:
                comp.integrating_factor = nu * comp.k2() ** vo

    def RHS(self, data, deriv):
        """
        Compute right hand side of fluid equations, populating deriv with
        the time derivatives of the fields.

        u_t + nu k^2 u = -ugradu - i k p / rho0

        """
        Physics.RHS(data, deriv)

        self.ugradu(data, deriv)
        self.pressure(data, deriv)


    def ugradu(self, data, deriv):
        # Place references
        k2 = data['u']['x'].k2()
        u = data['u']
        ucopy = self.aux_fields['ucopy']
        ugradu = self.aux_fields['ugradu']
        mathtmp = self.aux_fields['mathtmp']
        self.XlistgradY([u], u, mathtmp, [ucopy],[ugradu])
        for i in self.dims:
            deriv['u'][i]['kspace'] -= ugradu[i]['kspace'] 

    def pressure(self, data, deriv):
        """
        Compute pressure term for ufields: i k p / rho0

        p / rho0 = i k * ugradu / k^2
        ==> pressure term = - k (k * ugradu) / k^2

        """
        # Place references
        pressure = self.aux_fields['pressure']

        # Setup temporary data container
        sampledata = data['u']['x']
        tmp = na.zeros_like(sampledata.kdata)
        k2 = sampledata.k2(no_zero=True)

        # Construct k * ugradu
        for i in self.dims:
            tmp += data['u'][i].k[self._trans[i]] * deriv['u'][i]['kspace']

        # apply it
        for i in self.dims:
            deriv['u'][i]['kspace'] -= data['u'][i].k[self._trans[i]] * tmp / k2

class ShearIncompressibleHydro(IncompressibleHydro):
    """Incompressible hydrodynamics in a shearing box."""

    allowable_representations = [FourierShearRepresentation]

    def RHS(self, data, deriv):
        """
        Compute right hand side of fluid equations, populating deriv with
        the time derivatives of the fields.

        u_t + nu K^2 u = -ugradu - i K p / rho0 + rotation + shear

        rotation = -2 Omega u_x e_y
        shear = (2 + S) Omega u_y e_x

        """
        Physics.RHS(self, data, deriv)
        # Place references
        S = self.parameters['S']
        Omega = self.parameters['Omega']

        # Compute terms
        self.ugradu(data, deriv)
        self.shear_rotation(data, deriv)
        self.pressure(data, deriv)

        # Recalculate integrating factors
        self._setup_integrating_factors(deriv)

    def shear_rotation(self, data, deriv):
        """add shear and rotation terms
        """
        deriv['u']['y']['kspace'] += -2. * Omega * data['u']['x']['kspace']
        deriv['u']['x']['kspace'] += (2. + S) * Omega * data['u']['y']['kspace']


class BoussinesqHydro(IncompressibleHydro):
    def __init__(self, *args, **kwargs):
        Physics.__init__(self, *args, **kwargs)

        # Setup data fields
        self.fields = [('u', 'VectorField'),
                       ('T', 'ScalarField')]
        self._aux_fields = [('pressure', 'VectorField'),
                            ('mathtmp', 'ScalarField'),
                            ('ucopy','VectorField'),
                            ('Tcopy','VectorField'),
                            ('ugradu', 'VectorField'),
                            ('ugradT', 'ScalarField')]

        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        self.parameters = {'rho0': 1.,
                           'viscosity_order': 1,
                           'nu': 0.,
                           'kappa': 0.,
                           'g': 1.,
                           'alpha_t': 1.,
                           'beta': 1.}

        self.ThermalDrive = None

    def _setup_integrating_factors(self, deriv):

        # Kinematic viscosity for u
        IncompressibleHydro._setup_integrating_factors(self, deriv)

        # Thermal diffusivity for T
        comp = deriv['T'][0]
        kappa = self.parameters['kappa']
        vo = self.parameters['viscosity_order']
        if kappa == 0.:
            comp.integrating_factor = None
        else:
            comp.integrating_factor = kappa * comp.k2() ** vo

    def set_thermal_drive(self, func):
        self.ThermalDrive = func

    def RHS(self, data, deriv):
        """
        Compute right hand side of fluid equations, populating deriv with
        the time derivatives of the fields.

        u_t + nu k^2 u = -ugradu - i k p / rho0 + buoyancy
        T_t + kappa k^2 T = -ugradT + stratification term

        """
        Physics.RHS(self, data, deriv)

        self.ugradu(data, deriv)

        # temperature equation
        self.temperature(data, deriv)

        # add buoyancy term
        self.buoyancy(data, deriv)

        self.pressure(data, deriv)

    def buoyancy(self, data, deriv):
        g = self.parameters['g']
        alpha_t = self.parameters['alpha_t']

        u = data['u']
        T = data['T']
        deriv['u']['z']['kspace'] += g * alpha_t * T['kspace']        

    def temperature(self, data, deriv):
        beta = self.parameters['beta']
        u = data['u']
        T = data['T']
        mathtmp = self.aux_fields['mathtmp']
        Tcopy = self.aux_fields['Tcopy']
        ugradT = self.aux_fields['ugradT']

        self.XlistgradY([u], T, mathtmp, [Tcopy], [ugradT])
        deriv['T']['kspace'] = -ugradT['kspace'] - beta * u['z']['kspace']

        if self.ThermalDrive:
            deriv['T']['kspace'] += self.ThermalDrive(data)
        deriv['T']['kspace'][0,0,0] = 0. # must ensure (0,0,0) T mode does not grow.

class IncompressibleMHD(IncompressibleHydro):
    """Incompressible magnetohydrodynamics."""

    def __init__(self, *args, **kwargs):
        Physics.__init__(self, *args, **kwargs)

        # Setup data fields
        self.fields = [('u', 'VectorField'),
                       ('B', 'VectorField')]
        self._aux_fields = [('Ptotal', 'VectorField'),
                            ('mathtmp', 'ScalarField'),
                            ('ucopy','VectorField'),
                            ('Bcopy','VectorField'),
                            ('ugradu', 'VectorField'),
                            ('BgradB', 'VectorField'),
                            ('ugradB', 'VectorField'),
                            ('Bgradu', 'VectorField')]

        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        self.parameters = {'rho0': 1.,
                           'viscosity_order': 1,
                           'nu': 0.,
                           'eta': 0.}

    def _setup_integrating_factors(self, deriv):

        # Kinematic viscosity for u
        IncompressibleHydro._setup_integrating_factors(self)

        # Magnetic diffusivity for B
        for cindex, comp in deriv['B']:
            eta = self.parameters['eta']
            vo = self.parameters['viscosity_order']
            if eta == 0.:
                comp.integrating_factor = None
            else:
                comp.integrating_factor = eta * comp.k2() ** vo

    def RHS(self, data, deriv):
        """
        Compute right hand side of fluid equations, populating deriv with
        the time derivatives of the fields.

        u_t + nu k^2 u = -ugradu + BgradB / (4 pi rho0) - i k Ptot / rho0

        B_t + eta k^2 B = Bgradu - ugradB

        """

        if not self._finalized:
            self._finalize_init()
            self._setup_integrating_factors(deriv)

        deriv.set_time(data.time)
        self.aux_fields.set_time(data.time)

        # Place references
        u = data['u']
        B = data['B']
        mathtmp = self.aux_fields['mathtmp']
        ugradu = self.aux_fields['ugradu']
        BgradB = self.aux_fields['BgradB']
        ugradB = self.aux_fields['ugradB']
        Bgradu = self.aux_fields['Bgradu']
        Ptotal = self.aux_fields['Ptotal']
        ucopy = self.aux_fields['ucopy']
        Bcopy = self.aux_fields['Bcopy']
        pr4 = 4 * na.pi * self.parameters['rho0']
        k2 = data['u']['x'].k2()

        # Compute terms
        self.XlistgradY([u, B], u, mathtmp, [ucopy, Bcopy], [ugradu, Bgradu])
        self.XlistgradY([u, B], B, mathtmp, [ucopy, Bcopy], [ugradB, BgradB])
        self.total_pressure(data)

        # Construct time derivatives
        for i in self.dims:
            deriv['u'][i]['kspace'] = (-ugradu[i]['kspace'] +
                                        BgradB[i]['kspace'] / pr4 -
                                        Ptotal[i]['kspace'])

            deriv['B'][i]['kspace'] = Bgradu[i]['kspace'] - ugradB[i]['kspace']

    def total_pressure(self, data):
        """
        Compute total pressure term (including magnetic): i k Ptot / rho0

        Ptot / rho0 = i (k * ugradu - k * BgradB / (4 pi rho0)) / k^2
        ==> pressure term = - k (k * ugradu - k * BgradB / (4 pi rho0)) / k^2

        """

        # Place references
        ugradu = self.aux_fields['ugradu']
        BgradB = self.aux_fields['BgradB']
        Ptotal = self.aux_fields['Ptotal']
        pr4 = 4 * na.pi * self.parameters['rho0']

        # Setup temporary data container
        sampledata = data['u']['x']
        tmp = data.create_tmp_data('kspace')
        k2 = sampledata.k2(no_zero=True)

        # Construct k * ugradu - k * BgradB / (4 pi rho0)
        for i in self.dims:
            tmp += data['u'][i].k[self._trans[i]] * ugradu[i]['kspace']
            tmp -= data['u'][i].k[self._trans[i]] * BgradB[i]['kspace'] / pr4

        # Construct full term
        for i in self.dims:
            Ptotal[i]['kspace'] = -data['u'][i].k[self._trans[i]] * tmp / k2
            #Ptotal[i].zero_nyquist()

class ShearIncompressibleMHD(IncompressibleMHD):
    """Incompressible magnetohydrodynamics in a shearing box."""

    def RHS(self, data, deriv):
        """
        Compute right hand side of fluid equations, populating deriv with
        the time derivatives of the fields.

        u_t + nu k^2 u = -ugradu + BgradB / (4 pi rho0) - i k Ptot / rho0 + rotation + shear

        rotation = -2 Omega u_x e_y
        shear =  (2 + S) Omega u_y e_x

        B_t + eta k^2 B = Bgradu - ugradB + shear

        shear = -S Omega B_y e_x

        """

        # Place references
        S = self.parameters['S']
        Omega = self.parameters['Omega']

        # Compute terms
        MHD.RHS(self, data, deriv)
        deriv['u']['y']['kspace'] += -2. * Omega * data['u']['x']['kspace']
        deriv['u']['x']['kspace'] += (2 + S) * Omega * data['u']['y']['kspace']
        deriv['B']['x']['kspace'] += -S * Omega * data['B']['y']['kspace']

        # Recalculate integrating factors
        self._setup_integrating_factors(deriv)

    def total_pressure(self, data):
        """
        Compute total pressure term (including magnetic): i k Ptot / rho0

        Ptot / rho0 = i (k * ugradu - k * BgradB / (4 pi rho0) + rotation + shear) / k^2
        ==> pressure term = - k (k * ugradu - k * BgradB / (4 pi rho0) + rotation + shear) / k^2

        rotation = 2 Omega u_x K_y
        shear = -(1 + S) 2 Omega u_y K_x

        """

        # Place references
        ugradu = self.aux_fields['ugradu']
        BgradB = self.aux_fields['BgradB']
        Ptotal = self.aux_fields['Ptotal']
        pr4 = 4 * na.pi * self.parameters['rho0']
        S = self.parameters['S']
        Omega = self.parameters['Omega']


        # Setup temporary data container
        sampledata = data['u']['x']
        tmp = data.create_tmp_data('kspace')
        k2 = sampledata.k2(no_zero=True)

        # Construct k * ugradu - k * BgradB / (4 pi rho0)
        for i in self.dims:
            tmp += data['u'][i].k[self._trans[i]] * ugradu[i]['kspace']
            tmp -= data['u'][i].k[self._trans[i]] * BgradB[i]['kspace'] / pr4

        # Add rotation + shear
        tmp += (-2. * (1 + S) * Omega * data['u']['y'].k['x'] * data['u']['y']['kspace'] +
                2. * Omega * data['u']['x'].k['y'] * data['u']['x']['kspace'])

        # Construct full term
        for i in self.dims:
            Ptotal[i]['kspace'] = -data['u'][i].k[self._trans[i]] * tmp / k2
            #Ptotal[i].zero_nyquist()


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
    def __init__(self, *args, **kwargs):
        Physics.__init__(self, *args, **kwargs)
        self.fields = [('delta', 'ScalarField'),
                       ('u', 'VectorField')]
        self._aux_fields = [('gradphi', 'VectorField')]

        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        params = {'Omega_r': 0.,
                  'Omega_m': 0.,
                  'Omega_l': 0.,
                  'H0': 100.}
        self._setup_parameters(params)
        self._setup_aux_fields(0., self._aux_fields)
        aux_eqn_rhs = a_friedmann
        self._setup_aux_eqns(['a'], [aux_eqn_rhs], [0.002],
                             [self.parameters])

        self._RHS = self.create_fields(0.)

    def RHS(self, data):
        self.density_RHS(data)
        self.vel_RHS(data)
        self._RHS.time = data.time
        return self._RHS

    def density_RHS(self, data):
        a = self.aux_eqns['a'].value
        divu = na.zeros(data['delta'].shape, complex)
        for i in self.dims:
            divu += data['u'][i].deriv(self._trans[i])

        self._RHS['delta']['kspace'] = -divu / a

    def vel_RHS(self, data):
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']
        a = self.aux_eqns['a'].value
        adot = self.aux_eqns['a'].RHS(a)
        for i in self.dims:
            self._RHS['u'][i]['kspace'] = (-gradphi[i]['kspace'] -
                                            adot * data['u'][i]['kspace']) / a

    def grad_phi(self, data):
        a  = self.aux_eqns['a'].value
        H  = self.aux_eqns['a'].RHS(a) / a
        H0 = self.parameters['H0']
        Om = self.parameters['Omega_m']

        gradphi = self.aux_fields['gradphi']
        tmp = (-3./2. * H0*H0/a * Om * data['delta']['kspace'] /
                data['delta'].k2(no_zero=True))

        for i in self.dims:
            gradphi[i]['kspace'] = 1j * data['u'][i].k[self._trans[i]] * tmp

class CollisionlessCosmology(LinearCollisionlessCosmology):
    """This class implements collisionless cosmology with nonlinear terms.

    solves
    ------
    d_t d = -(1 + d) div(v_) / a - v dot grad(d) / a
    d_t v = -grad(Phi) / a - H v -(v dot grad) v / a
    laplacian(Phi) = 3 H^2 d / 2
    """

    def __init__(self, *args, **kwargs):
        LinearCollisionlessCosmology.__init__(self, *args, **kwargs)
        self._aux_fields.append(('math_tmp', 'ScalarField'))
        self._aux_fields.append(('ugraddelta', 'ScalarField'))
        self._aux_fields.append(('divu', 'ScalarField'))
        self._aux_fields.append(('deltadivu', 'ScalarField'))
        self._aux_fields.append(('ugradu', 'VectorField'))
        self._setup_aux_fields(0., self._aux_fields) # re-creates gradphi

    def delta_div_u(self, data, compute_divu=False):
        """calculate delta*div(v) in x-space, using 2/3 de-aliasing

        """
        divu = self.aux_fields['divu']
        if compute_divu:
            self.divX(data['u'], divu)
        divu = self.aux_fields['divu']
        deltadivu = self.aux_fields['deltadivu']

        deltadivu.zero()
        deltadivu['xspace'] += divu['xspace'] * data['delta']['xspace']

    def RHS(self, data):
        self.density_RHS(data)
        self.vel_RHS(data)
        self._RHS.time = data.time
        return self._RHS

    def density_RHS(self, data):
        a = self.aux_eqns['a'].value
        divu = self.aux_fields['divu']
        self.divX(data['u'], divu)
        self.XlistgradY([data['u'],], data['delta'],
                        self.aux_fields['math_tmp'],
                        [self.aux_fields['ugraddelta'],])
        self.delta_div_u(data)
        ugraddelta = self.aux_fields['ugraddelta']
        deltadivu = self.aux_fields['deltadivu']

        self._RHS['delta']['kspace'] = -(divu['kspace'] +
                                         deltadivu['kspace'] +
                                         ugraddelta['kspace']) / a

    def vel_RHS(self, data):
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']

        a = self.aux_eqns['a'].value
        adot = self.aux_eqns['a'].RHS(a)

        self.XlistgradY([data['u'],], data['u'],
                        self.aux_fields['math_tmp'],
                        [self.aux_fields['ugradu'],])

        ugradu = self.aux_fields['ugradu']

        for i in self.dims:
            self._RHS['u'][i]['kspace'] = -(gradphi[i]['kspace'] +
                                            adot * data['u'][i]['kspace'] +
                                            ugradu[i]['kspace']) / a

class LinearBaryonCDMCosmology(Physics):
    """This class implements linear cosmology for coupled baryon and CDM fluids.

    parameters
    ----------
    Omega_r - energy density in radiation
    Omega_m - energy density in matter
    Omega_b - energy density in baryons
    Omega_c - energy density in CDM
    Omega_l - energy density in dark energy (cosmological constant)
    H0      - hubble constant now

    solves
    ------
    d_t d_c = -div(v_c) / a
    d_t v_c = -grad(Phi) / a - H v_c

    d_t d_b = -div(v_b) / a
    d_t v_b = -grad(Phi) / a - H v_b
              - c_s^2 grad(d_b) / a

    laplacian(Phi) = 3/2 H^2 (Omega_c * d_c + Omega_b * d_b)/Omega_m
    """

    def __init__(self, *args, **kwargs):
        Physics.__init__(self, *args, **kwargs)
        self.fields = [('delta_b', 'ScalarField'),
                       ('u_b', 'VectorField'),
                       ('delta_c', 'ScalarField'),
                       ('u_c', 'VectorField')]
        self._aux_fields = [('gradphi', 'VectorField')]
        self._aux_fields.append(('graddelta_b', 'VectorField'))
        self._aux_fields.append(('divu_b', 'ScalarField'))
        self._aux_fields.append(('divu_c', 'ScalarField'))
        self._setup_aux_fields(0., self._aux_fields)

        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        params = {'Omega_r': 0.,
                  'Omega_m': 0.,
                  'Omega_b': 0.,
                  'Omega_c': 0.,
                  'Omega_l': 0.,
                  'H0': 7.185e-5} # 70.3 km/s/Mpc in Myr^-1
        self._setup_parameters(params)
        self._setup_aux_fields(0., self._aux_fields)
        aux_eqn_rhs = a_friedmann
        self._setup_aux_eqns(['a'], [aux_eqn_rhs], [0.002],
                             [self.parameters])
        self._RHS = self.create_fields(0.)

        self._cs2_a = []
        self._cs2_values = []

    def init_cs2(self, a, cs2):
        self._cs2_values = cs2
        self._cs2_a = a

    def cs2_at(self, a):
        """look up cs2 in internal table at nearest scale factor. Uses
        binary search to find the correct index.

        """
        lower = 0
        upper = len(self._cs2_a)
        i = 0
        while True:
            if a > self._cs2_a[i]:
                lower = i
                i = lower + int(na.ceil((upper - lower)/2.))
            elif a < self._cs2_a[i]:
                upper = i
                i = upper - int(na.ceil((upper - lower)/2.))

            if i == len(self._cs2_a):
                print "warning: scale factor out of cs2 range; using sound speed at a = ", self._cs2_a[-1]
                return self._cs2_values[-1]

            if lower >= upper - 1:
                return self._cs2_values[i]

    def RHS(self, data):
        self.d_b_RHS(data)
        self.d_c_RHS(data)
        self.v_b_RHS(data)
        self.v_c_RHS(data)
        self._RHS.time = data.time
        return self._RHS

    def d_b_RHS(self, data):
        a = self.aux_eqns['a'].value
        u = data['u_b']
        delta = data['delta_b']
        divu = self.aux_fields['divu_b']

        self.divX(u, divu)

        self._RHS['delta_b']['kspace'] = -(divu['kspace']) / a

    def d_c_RHS(self, data):
        a = self.aux_eqns['a'].value
        u = data['u_c']
        delta = data['delta_c']
        divu = self.aux_fields['divu_c']

        self.divX(u, divu)

        self._RHS['delta_c']['kspace'] = -(divu['kspace']) / a

    def grad_phi(self, data):
        a = self.aux_eqns['a'].value
        H = self.aux_eqns['a'].RHS(a) / a
        H0 = self.parameters['H0']

        sampledata = data['delta_c']

        gradphi = self.aux_fields['gradphi']
        tmp = (-3./2. * H0*H0/a *
                ((self.parameters['Omega_c'] * data['delta_c']['kspace'] +
                  self.parameters['Omega_b'] * data['delta_b']['kspace'])) /
                sampledata.k2(no_zero=True))

        for i in self.dims:
            gradphi[i]['kspace'] = 1j * sampledata.k[self._trans[i]] * tmp

    def v_b_RHS(self, data):
        # needs pressure term
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']

        a = self.aux_eqns['a'].value
        adot = self.aux_eqns['a'].RHS(a)

        u = data['u_b']
        graddelta = self.aux_fields['graddelta_b'] # calculated in d_b_RHS
        cs2 = self.cs2_at(a)
        for i in self.dims:
            self._RHS['u_b'][i]['kspace'] = -(gradphi[i]['kspace'] +
                                             adot * u[i]['kspace'] +
                                             cs2 * graddelta[i]['kspace']) / a

    def v_c_RHS(self, data):
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']

        a = self.aux_eqns['a'].value
        adot = self.aux_eqns['a'].RHS(a)

        u = data['u_c']
        for i in self.dims:
            self._RHS['u_c'][i]['kspace'] = -(gradphi[i]['kspace'] +
                                             adot * u[i]['kspace']) / a

class BaryonCDMCosmology(Physics):
    """This class implements cosmology for coupled baryon and CDM fluids.

    parameters
    ----------
    Omega_r - energy density in radiation
    Omega_m - energy density in matter
    Omega_b - energy density in baryons
    Omega_c - energy density in CDM
    Omega_l - energy density in dark energy (cosmological constant)
    H0      - hubble constant now

    solves
    ------
    d_t d_c = -(1 + d_c) div(v_c) / a - v_c dot grad(d_c) / a
    d_t v_c = -grad(Phi) / a - H v_c -(v_c dot grad) v_c / a

    d_t d_b = -(1 + d_b) div(v_b) / a - v_b dot grad(d_b) / a
    d_t v_b = -grad(Phi) / a - H v_b -(v_b dot grad) v_b / a
              - c_s^2 grad(d_b) / a

    laplacian(Phi) = 3/2 H^2 (Omega_c * d_c + Omega_b * d_b)/Omega_m
    """

    def __init__(self, *args, **kwargs):
        Physics.__init__(self, *args, **kwargs)
        self.fields = [('delta_b', 'ScalarField'),
                       ('u_b', 'VectorField'),
                       ('delta_c', 'ScalarField'),
                       ('u_c', 'VectorField')]
        self._aux_fields = [('gradphi', 'VectorField')]
        self._aux_fields.append(('graddelta_b', 'VectorField'))
        self._aux_fields.append(('ugraddelta_b', 'ScalarField'))
        self._aux_fields.append(('ugraddelta_c', 'ScalarField'))
        self._aux_fields.append(('divu_b', 'ScalarField'))
        self._aux_fields.append(('divu_c', 'ScalarField'))
        self._aux_fields.append(('deltadivu_b', 'ScalarField'))
        self._aux_fields.append(('deltadivu_c', 'ScalarField'))
        self._aux_fields.append(('math_tmp', 'ScalarField'))
        self._aux_fields.append(('ugradu_b', 'VectorField'))
        self._aux_fields.append(('ugradu_c', 'VectorField'))
        self._aux_fields.append(('math_tmp', 'ScalarField'))
        self._setup_aux_fields(0., self._aux_fields)

        self._trans = {0: 'x', 1: 'y', 2: 'z'}
        params = {'Omega_r': 0.,
                  'Omega_m': 0.,
                  'Omega_b': 0.,
                  'Omega_c': 0.,
                  'Omega_l': 0.,
                  'H0': 7.185e-5} # 70.3 km/s/Mpc in Myr^-1
        self._setup_parameters(params)
        self._setup_aux_fields(0., self._aux_fields)
        aux_eqn_rhs = a_friedmann
        self._setup_aux_eqns(['a'], [aux_eqn_rhs], [0.002],
                             [self.parameters])
        self._RHS = self.create_fields(0.)

        self._cs2_a = []
        self._cs2_values = []

    def init_cs2(self, a, cs2):
        self._cs2_values = cs2
        self._cs2_a = a

    def cs2_at(self, a):
        """look up cs2 in internal table at nearest scale factor. Uses
        binary search to find the correct index.

        """
        lower = 0
        upper = len(self._cs2_a)
        i = 0
        while True:
            if a > self._cs2_a[i]:
                lower = i
                i = lower + int(na.ceil((upper - lower)/2.))
            elif a < self._cs2_a[i]:
                upper = i
                i = upper - int(na.ceil((upper - lower)/2.))

            if i == len(self._cs2_a):
                print "warning: scale factor out of cs2 range; using sound speed at a = ", self._cs2_a[-1]
                return self._cs2_values[-1]

            if lower >= upper - 1:
                return self._cs2_values[i]

    def RHS(self, data):
        self.d_b_RHS(data)
        self.d_c_RHS(data)
        self.v_b_RHS(data)
        self.v_c_RHS(data)
        self._RHS.time = data.time
        return self._RHS

    def d_b_RHS(self, data):
        a = self.aux_eqns['a'].value
        u = data['u_b']
        delta = data['delta_b']
        divu = self.aux_fields['divu_b']
        graddelta = self.aux_fields['graddelta_b']
        ugraddelta = self.aux_fields['ugraddelta_b']
        deltadivu = self.aux_fields['deltadivu_b']

        self.divX(u, divu)
        # compute both graddelta and ugraddelta
        self.XgradY(u, delta, graddelta, ugraddelta)
        deltadivu.zero()
        deltadivu['xspace'] += divu['xspace'] * delta['xspace']

        self._RHS['delta_b']['kspace'] = -(divu['kspace'] +
                                           deltadivu['kspace'] +
                                           ugraddelta['kspace']) / a

    def d_c_RHS(self, data):
        a = self.aux_eqns['a'].value
        u = data['u_c']
        delta = data['delta_c']
        divu = self.aux_fields['divu_c']
        math_tmp = self.aux_fields['math_tmp']
        ugraddelta = self.aux_fields['ugraddelta_c']
        deltadivu = self.aux_fields['deltadivu_c']

        self.divX(u, divu)
        self.XlistgradY([u,], delta, math_tmp, [ugraddelta,])
        deltadivu.zero()
        deltadivu['xspace'] += divu['xspace'] * delta['xspace']

        self._RHS['delta_c']['kspace'] = -(divu['kspace'] +
                                           deltadivu['kspace'] +
                                           ugraddelta['kspace']) / a

    def grad_phi(self, data):
        a = self.aux_eqns['a'].value
        H = self.aux_eqns['a'].RHS(a) / a
        H0 = self.parameters['H0']

        sampledata = data['delta_c']

        gradphi = self.aux_fields['gradphi']
        tmp = (-3./2. * H0*H0/a *
                ((self.parameters['Omega_c'] * data['delta_c']['kspace'] +
                  self.parameters['Omega_b'] * data['delta_b']['kspace'])) /
                sampledata.k2(no_zero=True))

        for i in self.dims:
            gradphi[i]['kspace'] = 1j * sampledata.k[self._trans[i]] * tmp

    def v_b_RHS(self, data):
        # needs pressure term
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']

        a = self.aux_eqns['a'].value
        adot = self.aux_eqns['a'].RHS(a)

        u = data['u_b']
        math_tmp = self.aux_fields['math_tmp']
        ugradu = self.aux_fields['ugradu_b']
        self.XlistgradY([u,], u, math_tmp, [ugradu,])
        graddelta = self.aux_fields['graddelta_b'] # calculated in d_b_RHS
        cs2 = self.cs2_at(a)
        for i in self.dims:
            self._RHS['u_b'][i]['kspace'] = -(gradphi[i]['kspace'] +
                                             adot * u[i]['kspace'] +
                                             ugradu[i]['kspace'] +
                                             cs2 * graddelta[i]['kspace']) / a

    def v_c_RHS(self, data):
        self.grad_phi(data)
        gradphi = self.aux_fields['gradphi']

        a = self.aux_eqns['a'].value
        adot = self.aux_eqns['a'].RHS(a)

        u = data['u_c']
        math_tmp = self.aux_fields['math_tmp']
        ugradu = self.aux_fields['ugradu_c']
        self.XlistgradY([u,], u, math_tmp, [ugradu,])
        for i in self.dims:
            self._RHS['u_c'][i]['kspace'] = -(gradphi[i]['kspace'] +
                                             adot * u[i]['kspace'] +
                                             ugradu[i]['kspace']) / a

if __name__ == "__main__":
    import pylab as P
    from representations import FourierData
    from init_cond import taylor_green
    a = Hydro((100,100),FourierData)
    data = a.create_fields(0.)
    taylor_green(data['ux'],data['uy'])
    vgv = a.ugradu(data)
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
