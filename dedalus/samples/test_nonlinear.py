from dedalus.mods import *
import numpy as na
import sys
import pylab as pl

if len(sys.argv) != 3:
    print "usage: ", sys.argv[0], " <ic data file> <normalization data file>"
    print """sample ic and normalization data are included in files
ic_input.txt (generated by linger++, linger-mode output with parameters in ic_param.inp)
norm_input.txt (generated by linger++, transfer-mode output)
"""
    sys.exit()

icfname = sys.argv[1]
normfname = sys.argv[2]

shape = (32,32,32)
L = (1000,)*3
RHS = CollisionlessCosmology(shape, FourierRepresentation, length=L)
data = RHS.create_fields(0.)
H0 = 7.185e-5 # 70.3 km/s/Mpc in Myr
a_i = 0.002 # initial scale factor
t0 = (2./3.)/H0 # present age of E-dS universe
t_ini = (a_i**(3./2.)) * t0 # time at which a = a_i

def pow_spec(data, it, Dplus, spec_delta, a):
    delta = data['u']['x']
    
    power = na.abs(delta['kspace'])**2

    kmag = na.sqrt(delta.k2())
    s_power = na.abs(spec_delta)**2

    k = delta.k['x'].flatten()
    k = na.abs(k[0:(k.size / 2 + 1)])
    kbottom = k - k[1] / 2.
    ktop = k + k[1] / 2.
    spec = na.zeros_like(k)
    s_spec = na.zeros_like(k)

    for i in xrange(k.size):
        kshell = (kmag >= kbottom[i]) & (kmag < ktop[i])
        nk = ((kshell & (power>0)) * na.ones_like(kmag)).sum()
        spec[i] = (power[kshell]).sum()/(Dplus*Dplus)/nk
        s_spec[i] = (s_power[kshell]).sum()/nk
    outfile = "frames/powspec_a%05f.png" % a
    fig = pl.figure()
    pl.loglog(k[1:], spec[1:], 'o-')
    #pl.loglog(k[1:], s_spec[1:], hold=True)
    pl.xlabel("$k$")
    pl.ylabel("$\mid \delta_k \mid^2 / D_+^2$")
    fig.savefig(outfile)

RHS.parameters['Omega_r'] = 0.#8.4e-5
RHS.parameters['Omega_m'] = 1.#0.276
RHS.parameters['Omega_l'] = 0.#0.724
RHS.parameters['H0'] = H0

spec_delta, spec_u = cosmo_spectra(data, icfname, normfname)
collisionless_cosmo_fields(data['delta'], data['u'], spec_delta, spec_u)

dt = 10. # time in Myr
ti = RK4simplevisc(RHS)
ti.stop_time(100.*dt)
ti.set_nsnap(100)
ti.set_dtsnap(100)

an = AnalysisSet(data, ti)

an.add("field_snap", 20)
an.add("en_spec", 20)
i=0
an.run()
outfile = open('ugrowth.dat','w')
while ti.ok:
    Dplus = ((data.time + t_ini)/t_ini) ** (2./3.)
    adot = RHS.aux_eqns['a'].RHS(RHS.aux_eqns['a'].value)
    print 'step: ', i, ' a = ', RHS.aux_eqns['a'].value
    if i % 1 == 0:
        pow_spec(data, i, adot, spec_delta, RHS.aux_eqns['a'].value)
    ti.advance(data, dt)
    i = i + 1
    an.run()
    u = data['u'][0]['kspace'][9,9,9].real
    print u
    outfile.write("%10.5e\t%10.5e\t%10.5e\n" %(ti.time, adot, u))
outfile.close()
pow_spec(data, i, Dplus, spec_delta, RHS.aux_eqns['a'].value)
    
