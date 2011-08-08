from dedalus.mods import *
import numpy as na
import sys

if len(sys.argv) != 3:
    print "usage: ", sys.argv[0], " <ic data file> <normalization data file>"
    print """sample ic and normalization data are included in files
ic_input.txt (generated by linger++, linger-mode output with parameters in ic_param.inp)
norm_input.txt (generated by linger++, transfer-mode output)
"""
    sys.exit()

icfname = sys.argv[1]
normfname = sys.argv[2]

shape = (10,10,10)
RHS = LinearCollisionlessCosmology(shape, FourierRepresentation)
data = RHS.create_fields(0.)
RHS.parameters['Omega_r'] = 8.4e-5
RHS.parameters['Omega_m'] = 0.276
RHS.parameters['Omega_l'] = 0.724
RHS.parameters['H0'] = 7.185e-5 # 70.3 km/s/Mpc in Myr

spec_delta, spec_u = cosmo_spectra(data, icfname, normfname)
collisionless_cosmo_fields(data['delta'], data['u'], spec_delta, spec_u)

ti = RK4simplevisc(RHS)
ti.stop_time(1000)
ti.set_nsnap(100)
ti.set_dtsnap(1000)
dt = 1 # time in Myr

outfile = open('growth.dat','w')

delta_init = na.zeros_like(data['delta']['kspace'])
ti.advance(data, dt) 
# May need to advance more for the decaying mode to vanish completely
delta_init[:] = data['delta']['kspace']
while ti.ok:
    ti.advance(data, dt)
    delta = data['delta']['kspace'][1,1,1].real
    outfile.write("%10.5e\t%10.5e\t%10.5e\n" %(ti.time, ti.RHS.aux_eqns['a'].value, delta))
outfile.close()

delta_final = data['delta']['kspace'] 
#print delta_final/delta_init
#Should be a single real number for all modes, assuming the decaying
#solution is negligible in delta_init
