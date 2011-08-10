"""Test of linearized cosmology with only CDM fluid

Authors: G. Peairs <gpeairs@stanford.edeu>
Affiliation: KIPAC/SLAC/Stanford
License:
  Copyright (C) 2011 J. S. Oishi, G. Peairs.  All Rights Reserved.

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

from dedalus.mods import *
import numpy as na
import sys

if len(sys.argv) != 2:
    print "usage: ", sys.argv[0], " <normalization data file>"
    print """sample ic and normalization data is included in file norm_input.txt (generated by linger++, transfer-mode output)
"""
    print "using sample data..."
    normfname = 'norm_input.txt'
else:
    normfname = sys.argv[1]

shape = (10,10,10)
RHS = LinearCollisionlessCosmology(shape, FourierRepresentation)
data = RHS.create_fields(0.)

H0 = 7.185e-5 # 70.3 km/s/Mpc in Myr^-1
a_i = RHS.aux_eqns['a'].value # initial scale factor
t0 = (2./3.)/H0 # present age of E-dS universe
t_ini = (a_i**(3./2.)) * t0 # time at which a = a_i (in Einstein-de Sitter)

RHS.parameters['Omega_r'] = 8.4e-5
RHS.parameters['Omega_m'] = 0.276
RHS.parameters['Omega_l'] = 0.724
RHS.parameters['H0'] = H0

spec_delta, spec_u = cosmo_spectra(data, normfname)
collisionless_cosmo_fields(data['delta'], data['u'], spec_delta, spec_u)

dt = 5. # time in Myr
ti = RK4simplevisc(RHS)
ti.stop_time(500)
ti.set_nsnap(100)
ti.set_dtsnap(1000)

an = AnalysisSet(data, ti)

an.add("field_snap", 20)
an.add("compare_power", 20, {'f1':'delta', 'f2':'u'})

i=0
an.run()
while ti.ok:
    Dplus = ((data.time + t_ini)/t_ini) ** (2./3.)
    print 'step: ', i, ' a = ', RHS.aux_eqns['a'].value
    ti.advance(data, dt)
    i = i + 1
    an.run()    

