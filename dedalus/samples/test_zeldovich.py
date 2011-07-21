from dedalus.mods import *
import numpy as na
import pylab as pl

shape = (16,16,16)
RHS = CollisionlessCosmology(shape, FourierRepresentation)
data = RHS.create_fields(0.)
H_0 = 2.27826587e-18 # 70.3 km/s/Mpc in seconds^-1
ampl = 4e-19 # amplitude of initial velocity wave

L = 2*na.pi # size of box
N_p = 128 # resolution of analytic solution
q = na.array([i for i in xrange(0,N_p)]) * L / N_p
k = 2*na.pi/L # wavenumber of initial velocity perturbation
a_i = 0.002 # initial scale factor
t0 = (2./3.)/H_0 # present age of E-dS universe
t_init = (a_i**(3./2.)) * t0 # time at which a = a_i in this universe

Ddot_i = (2./3.) * ((1./t0)**(2./3.)) * (t_init**(-1./3.)) / a_i
A = ampl / a_i / Ddot_i
a_cross = a_i / (A * k)
print "a_cross = ", a_cross
tcross = (a_cross**(3./2.))*t0

RHS.parameters['Omega_r'] = 0#8.4e-5
RHS.parameters['Omega_m'] = 1#0.276
RHS.parameters['Omega_l'] = 0#0.724
RHS.parameters['H0'] = H_0
zeldovich(data, ampl)

Myr = 3.15e13 # 10^6 years in seconds
tstop = tcross
dt = Myr*1e1

ti = RK2simple(RHS)
ti.stop_time(tstop)
ti.set_nsnap(1000)
ti.set_dtsnap(1e19)

ddelta = []
uu = []
uk = []

t_snapshots = []
a_snapshots = []
  
an = AnalysisSet(data, ti)
an.add("field_snap", 20)
an.add("en_spec", 20)

i = 0
#an.run()
while ti.ok:
    print "step: ", i
    if i % 20 == 0:
        tmp = na.zeros_like(data['u'][0]['xspace'][0,0,:].real)
        tmp[:] = data['u'][0]['xspace'][0,0,:].real

        tmp2 = na.zeros_like(data['delta']['xspace'][0,0,:].real)
        tmp2[:] = data['delta']['xspace'][0,0,:].real

        tmp3 = na.zeros_like(data['u'][0]['kspace'][0,0,:].real)
        tmp3[:] = na.abs(data['u'][0]['kspace'][0,0,:])

        uu.append(tmp)
        ddelta.append(tmp2)
        uk.append(tmp3)
        t_snapshots.append(data.time)
        a_snapshots.append(RHS.aux_eqns['a'].value)
    ti.advance(data, dt)
    #an.run()
    i = i + 1
print "a_stop = ", RHS.aux_eqns['a'].value

def reorder(arr):
    di = len(arr)/2
    tmp = [arr[i-di] for i in xrange(len(arr))]
    return tmp 

pl.figure()
for i in xrange(len(ddelta)):
    pl.plot(reorder(ddelta[i]),hold=True)

pl.figure()
for i in xrange(len(uu)):
    pl.plot(reorder(uu[i]),hold=True)

pl.figure()
for i in xrange(len(uk)):
    pl.plot(reorder(uk[i])[(len(uk[i])/2):],hold=True)

pl.figure()
for t in t_snapshots:
    t = t + t_init
    a = (t/t0)**(2./3)
    D = a / a_i
    x = q + D*A*na.sin(k*q)
    Ddot = (2./3.) * ((1./t0)**(2./3.)) * (t**(-1./3.)) / a_i
    delta = 1./(1.+D*A*k*na.cos(k*q))-1.
    v = a * Ddot * A * na.sin(k*q)
    phi = 3/2/a * ( (q**2 - x**2)/2 + 
                    D * A * k * (k*q*na.sin(k*q) + na.cos(k*q) - 1) )
    pl.plot(x, v, hold=True)
pl.figure()
pl.plot(x, v, hold=True)
x = [2*na.pi*i/16. for i in xrange(16)]
pl.plot(x, reorder(uu[-1]), '.', hold=True)

pl.show()
