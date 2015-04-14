from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import range
from builtins import super
from future import standard_library
standard_library.install_aliases()

from nose.tools import raises, assert_raises

from itertools import chain
from friendlysam.optimization import (
    Problem, Minimize, Constraint, SolverError, Variable, PiecewiseAffine, SOS1, SOS2, Domain)
from friendlysam.tests import default_solver, approx
from friendlysam.compat import ignored


def test_simple_SOS1():
    n = 4
    index = 2
    sum_val = 3.
    vs = [Variable(lb=-1, domain=Domain.integer) for i in range(n)]
    #vs[0] = Variable(lb=-1, domain=Domain.integer)
    weights = [1 for i in range(n)]
    weights[index] = 0.5
    prob = Problem()
    prob.constraints.add(SOS1(vs))
    prob.constraints.add(Constraint(sum(vs) == sum_val))
    #prob.constraints.update(Constraint(v >= 0) for v in vs)
    prob.objective = Minimize(sum(v * w for v, w in zip(vs, weights)))

    solution = default_solver.solve(prob)
    print(solution)
    for v in vs:
        v.take_value(solution)

    for i in range(n):
        if i == index:
            assert(approx(vs[i].value, sum_val))
        else:
            assert(approx(vs[i].value, 0))


def test_simple_pwa():
    pwa = PiecewiseAffine((1, 1.5, 2), name='aoeu')
    prob = Problem()
    prob.constraints.update(pwa.constraints)
    prob.objective = Minimize(pwa.func([3, 2, 4]))

    solution = default_solver.solve(prob)
    print(solution)
    for w in pwa.weights:
        w.take_value(solution)

    assert(approx(pwa.arg.value, 1.5))


if __name__ == '__main__':
    test_simple_SOS1()