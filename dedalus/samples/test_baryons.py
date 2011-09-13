"""Test of cosmology with coupled baryon and CDM fluids

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
import pylab as pl
from dedalus.utils.parallelism import setup_parallel_objs

if len(sys.argv) != 3:
    print "usage: ", sys.argv[0], "<normalization data file> <thermal history data file>"
    print """sample ic and normalization data are included in file norm_input.txt (generated by linger++, transfer-mode output)
sample thermal history is provided in file thermal_history.txt (generated by linger++)"""
    print "using sample data..."
    normfname = 'norm_input.txt'
    thermofname = 'thermal_history.txt' # linger++ thermal history output
else:
    normfname = sys.argv[1]
    thermofname = sys.argv[2]

shape = (32,32,32)
L = (1000,)*3
shape, L = setup_parallel_objs(shape, L)
RHS = BaryonCDMCosmology(shape, ParallelFourierRepresentation, length=L)
data = RHS.create_fields(0.)
H0 = 7.185e-5 # 70.3 km/s/Mpc in Myr^-1
a_i = RHS.aux_eqns['a'].value # initial scale factor
t0 = (2./3.)/H0 # present age of E-dS universe (although we're using LCDM)
t_ini = (a_i**(3./2.)) * t0 # time at which a = a_i in E-dS

def read_cs2(thermo_fname):
    """read baryon sound speed squared from linger++ thermal history output

    """
    c = 0.3063015366 # speed of light in Mpc/Myr

    cs2 = []
    a = []
    for line in open(thermo_fname):
        values = line.split()
        a.append(float(values[1]))
        cs2.append(float(values[4])*c*c)
        
    return a, cs2

RHS.parameters['Omega_r'] = 8.4e-5
RHS.parameters['Omega_m'] = 0.276
RHS.parameters['Omega_b'] = 0.045
RHS.parameters['Omega_c'] = RHS.parameters['Omega_m'] - RHS.parameters['Omega_b']
RHS.parameters['Omega_l'] = 0.724
RHS.parameters['H0'] = H0
a, cs2 = read_cs2(thermofname)
RHS.init_cs2(a, cs2)

spec_delta_c, spec_u_c, spec_delta_b, spec_u_b = cosmo_spectra(data, normfname, baryons=True)
cosmo_fields(data['delta_c'], data['u_c'], data['delta_b'], data['u_b'], spec_delta_c, spec_u_c, spec_delta_b, spec_u_b)

dt = 5. # time in Myr
ti = RK4simplevisc(RHS)
ti.stop_time(100.*dt)
ti.set_nsnap(100)
ti.set_dtsnap(10000)

an = AnalysisSet(data, ti)
an.add("field_snap", 10)
an.add("compare_power", 10)
i=0
an.run()
while ti.ok:
    Dplus = ((data.time + t_ini)/t_ini) ** (2./3.)
    print 'step: ', i, ' a = ', RHS.aux_eqns['a'].value
    ti.advance(data, dt)
    i = i + 1
    an.run()
