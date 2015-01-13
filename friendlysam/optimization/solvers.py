# -*- coding: utf-8 -*-

from friendlysam.log import get_logger
logger = get_logger(__name__)
from friendlysam.optimization.optimization import (
    RelConstraint, SOS1Constraint, SOS2Constraint, Sense)

import pyomo.environ
from pyomo.opt import SolverFactory

import operator

import sympy
from enum import Enum

DEFAULT_SOLVER_ORDER = ('gurobi', 'cbc')
solver_order = DEFAULT_SOLVER_ORDER

_solver_funcs = {
    'gurobi': lambda: PyomoSolver('gurobi', solver_io='python'),
    'cbc': lambda: PyomoSolver('cbc', solver_io='asl')
    }

def get_solver(*names):
    if len(names) == 0:
        names = solver_order

    for name in names:
        try:
            return _solver_funcs[name]()
        except SolverNotAvailableError:
            pass


class SolverNotAvailableError(Exception): pass

class SolverError(Exception): pass

class Solver(object):
    """Base class for optimization solvers

    This base class only defines the interface.
    """

    def __init__(self):
        """Create a new solver instance

        Raises:
            SolverNotAvailableError if the solver is not available.
        """
        super(Solver, self).__init__()

        
    def solve(self, problem):
        """Solve an optimization problem and return the solution

        Args:
            problem (Problem): The optimization problem to solve.

        Returns:
            A dict `{variable: value for variable in problem.variables}`

        Raises:
            SolverError if problem could not be solved.
        """
        raise NotImplementedError()

class PyomoExpressionError(Exception): pass

class PyomoSolver(Solver):
    """docstring for PyomoSolver"""

    def __init__(self, solver, **kwargs):
        """Create a new solver instance

        Raises:
            SolverNotAvailableError if the solver is not available.
        """
        super(PyomoSolver, self).__init__()
        self._solver = SolverFactory(solver, **kwargs)

    def _add_var(self):
        self._var_counter += 1
        name = 'v{}'.format(self._var_counter)
        var = pyomo.environ.Var()
        setattr(self._model, name, var)
        return var

    def _get_constraint_name(self):
        self._constraint_counter += 1
        return 'c{}'.format(self._constraint_counter)


    def solve(self, problem):
        self._constraint_counter = 0
        self._var_counter = 0
        self._model = pyomo.environ.ConcreteModel()
        
        self._pyomo_variables = {v: self._add_var() for v in problem.variables}

        self._set_objective(problem)

        map(self._add_constraint, problem.constraints)

        self._model.preprocess()

        result = self._solver.solve(self._model)

        if not result.Solution.Status == pyomo.opt.SolutionStatus.optimal:
            raise SolverError("pyomo solution status is '{0}'".format(result.Solution.Status))

        self._model.load(result)

        return {key: variable.value for key, variable in self._pyomo_variables.items()}

    def _add_constraint(self, c):
        original = c
        if isinstance(c, RelConstraint):
            c = c.expr

        if isinstance(c, sympy.Rel):
            expr = self._make_pyomo_relation(c)
            try:
                setattr(self._model, self._get_constraint_name(), pyomo.environ.Constraint(expr=expr))
            except ValueError, e:
                print(e)
                print(str(expr), str(original))
                raise e

        elif isinstance(c, SOS1Constraint):
            raise NotImplementedError()

        elif isinstance(c, SOS2Constraint):
            raise NotImplementedError()

        else:
            raise NotImplementedError()

    def _set_objective(self, problem):
        sense_translation = {
            Sense.minimize: pyomo.environ.minimize,
            Sense.maximize: pyomo.environ.maximize }
        expr = self._make_pyomo_poly(problem.objective)
        self._model.obj = pyomo.environ.Objective(expr=expr, sense=sense_translation[problem.sense])

    def _make_pyomo_poly(self, expr):
        symbols = sorted(expr.atoms(sympy.Symbol), key=lambda x: sympy.default_sort_key(x, 'lex'))

        variables = [self._pyomo_variables[s] for s in symbols]

        if len(symbols) == 0:
            return float(expr)

        polynomial = expr.as_poly(*symbols)
        if polynomial is None:
            raise ValueError('{} is not a sympy polynomial'.format(expr))

        terms = []

        for exponents, coeff in polynomial.terms():
            coeff = float(coeff)
            if all((e == 0 for e in exponents)):
                terms.append(coeff)
            else:
                factors = []
                for base, exponent in filter(lambda (a, e): e != 0, zip(variables, exponents)):
                    factors.extend([base] * exponent)
                terms.append(coeff * reduce(operator.mul, factors))
        return sum(terms)

    def _make_pyomo_relation(self, expr):

        if isinstance(expr, sympy.LessThan):
            a, b = expr.args
            return self._make_pyomo_poly(a - b) <= 0
            
        elif isinstance(expr, sympy.GreaterThan):
            a, b = expr.args
            return self._make_pyomo_poly(a - b) >= 0
            
        elif isinstance(expr, sympy.Equality):
            a, b = expr.args
            return self._make_pyomo_poly(a - b) == 0
            
        elif isinstance(expr, sympy.StrictGreaterThan) or isinstance(expr, sympy.StrictLessThan):
            raise PyomoExpressionError('Strict inequalities are not allowed.')

        else:
            raise PyomoExpressionError(
                'Expression "{}" ({}) cannot be translated.'.format(expr, type(expr)))