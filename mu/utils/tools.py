import bisect
import functools
import itertools
import math
import operator

import numpy as np
from scipy.stats import norm


def accumulate_from_zero(iterator: tuple) -> tuple:
    return tuple(itertools.accumulate((0,) + (tuple(iterator))))


def find_closest_index(item: float, data: tuple) -> int:
    """Return index of element in data with smallest difference to item"""
    solution = bisect.bisect_left(data, item)
    if solution == len(data):
        return solution - 1
    elif solution == 0:
        return solution
    else:
        indices = (solution, solution - 1)
        differences = tuple(abs(item - data[n]) for n in indices)
        return indices[differences.index(min(differences))]


def find_closest_item(item: float, data: tuple) -> float:
    """Return element in data with smallest difference to item"""
    return data[find_closest_index(item, data)]


def brownian(x0, n, dt, delta, out=None, random_state=None):
    """Generate an instance of Brownian motion (i.e. the Wiener process):

        X(t) = X(0) + N(0, delta**2 * t; 0, t)

    where N(a,b; t0, t1) is a normally distributed random variable with mean a and
    variance b.  The parameters t0 and t1 make explicit the statistical
    independence of N on different time intervals; that is, if [t0, t1) and
    [t2, t3) are disjoint intervals, then N(a, b; t0, t1) and N(a, b; t2, t3)
    are independent.

    Written as an iteration scheme,

        X(t + dt) = X(t) + N(0, delta**2 * dt; t, t+dt)


    If `x0` is an array (or array-like), each value in `x0` is treated as
    an initial condition, and the value returned is a numpy array with one
    more dimension than `x0`.

    Arguments
    ---------
    x0 : float or numpy array (or something that can be converted to a numpy array
         using numpy.asarray(x0)).
        The initial condition(s) (i.e. position(s)) of the Brownian motion.
    n : int
        The number of steps to take.
    dt : float
        The time step.
    delta : float
        delta determines the "speed" of the Brownian motion.  The random variable
        of the position at time t, X(t), has a normal distribution whose mean is
        the position at time t=0 and whose variance is delta**2*t.
    out : numpy array or None
        If `out` is not None, it specifies the array in which to put the
        result.  If `out` is None, a new numpy array is created and returned.

    Returns
    -------
    A numpy array of floats with shape `x0.shape + (n,)`.

    Note that the initial value `x0` is not included in the returned array.
    """

    x0 = np.asarray(x0)

    # For each element of x0, generate a sample of n numbers from a
    # normal distribution.
    r = norm.rvs(
        size=x0.shape + (n,), scale=delta * math.sqrt(dt), random_state=random_state
    )

    # If `out` was not given, create an output array.
    if out is None:
        out = np.empty(r.shape)

    # This computes the Brownian motion by forming the cumulative sum of
    # the random samples.
    np.cumsum(r, axis=-1, out=out)

    # Add the initial condition.
    out += np.expand_dims(x0, axis=-1)

    return out


def scale(a, minima=0, maxima=15):
    return np.interp(a, (a.min(), a.max()), (minima, maxima))


def graycode(length: int, modulus: int) -> tuple:
    """Returns the n-tuple reverse Gray code mod m.

    source: https://yetanothermathblog.com/tag/gray-codes/
    """
    n, m = length, modulus
    F = range(m)
    if n == 1:
        return [[i] for i in F]
    L = graycode(n - 1, m)
    M = []
    for j in F:
        M = M + [ll + [j] for ll in L]
    k = len(M)
    Mr = [0] * m
    for i in range(m - 1):
        i1 = i * int(k / m)
        i2 = (i + 1) * int(k / m)
        Mr[i] = M[i1:i2]
    Mr[m - 1] = M[(m - 1) * int(k / m) :]
    for i in range(m):
        if i % 2 != 0:
            Mr[i].reverse()
    M0 = []
    for i in range(m):
        M0 = M0 + Mr[i]
    return M0


def euclid(size: int, distribution: int) -> tuple:
    standard_size = size // distribution
    rest = size % distribution
    data = (standard_size for n in range(distribution))
    if rest:
        added = accumulate_from_zero(euclid(distribution, rest))
        return tuple(s + 1 if idx in added else s for idx, s in enumerate(data))
    else:
        return tuple(data)


def make_growing_series_with_sum_n(requested_sum: int) -> tuple:
    ls = []
    add_idx = iter([])
    while sum(ls) < requested_sum:
        try:
            ls[next(add_idx)] += 1
        except StopIteration:
            ls = [1] + ls
            add_idx = reversed(tuple(range(len(ls))))
    return tuple(ls)


def make_falling_series_with_sum_n(requested_sum: int) -> tuple:
    return tuple(reversed(make_growing_series_with_sum_n(requested_sum)))


def interlock_tuples(t0, t1) -> tuple:
    size0, size1 = len(t0), len(t1)
    difference = size0 - size1
    indices = functools.reduce(
        operator.add, ((0, 1) for n in range(min((size0, size1))))
    )
    if difference > 0:
        indices = tuple(0 for i in range(difference)) + indices
    else:
        indices = indices + tuple(1 for i in range(abs(difference)))
    t0_it = iter(t0)
    t1_it = iter(t1)
    return tuple(next(t0_it) if idx == 0 else next(t1_it) for idx in indices)


def not_fibonacci_transition(size0: int, size1: int, element0=0, element1=1) -> tuple:
    def write_to_n_element(it, element) -> tuple:
        return tuple(tuple(element for n in range(x)) for x in it)

    return functools.reduce(
        operator.add,
        interlock_tuples(
            *tuple(
                write_to_n_element(s, el)
                for s, el in zip(
                    (
                        make_falling_series_with_sum_n(size0),
                        make_growing_series_with_sum_n(size1),
                    ),
                    (element0, element1),
                )
            )
        ),
    )


def gcd(*arg):
    return functools.reduce(math.gcd, arg)


def lcm(*arg: int) -> int:
    """from

    https://stackoverflow.com/questions/37237954/
    calculate-the-lcm-of-a-list-of-given-numbers-in-python
    """
    lcm = arg[0]
    for i in arg[1:]:
        lcm = lcm * i // gcd(lcm, i)
    return lcm


def cyclic_permutation(iterable: tuple) -> tuple:
    return (iterable[x:] + iterable[0:x] for x in range(len(iterable)))


def backtracking(elements: tuple, tests: tuple, return_indices: bool = False) -> tuple:
    """General backtracking algorithm function."""

    def convert_indices2elements(indices: tuple) -> tuple:
        current_elements = tuple(elements)
        resulting_elements = []
        for idx in indices:
            resulting_elements.append(current_elements[idx])
            current_elements = tuple(
                p for i, p in enumerate(current_elements) if i != idx
            )
        return tuple(resulting_elements)

    def is_valid(indices: tuple) -> bool:
        resulting_elements = convert_indices2elements(tuple(element_indices))
        return all(tuple(test(resulting_elements) for test in tests))

    amount_available_elements = len(elements)
    aapppppi = tuple(reversed(tuple(range(1, amount_available_elements + 1))))
    element_indices = [0]
    while True:
        if is_valid(tuple(element_indices)):
            if len(element_indices) < amount_available_elements:
                element_indices.append(0)
            else:
                break
        else:
            while element_indices[-1] + 1 == aapppppi[len(element_indices) - 1]:
                element_indices = element_indices[:-1]
                if len(element_indices) == 0:
                    raise ValueError("No solution found")
            element_indices[-1] += 1

    res = convert_indices2elements(element_indices)
    if return_indices:
        return res, element_indices
    else:
        return res


def fib(x: int) -> int:
    """Fast fibonacci function

    written by https://www.codespeedy.com/find-fibonacci-series-in-python/
    """
    return round(math.pow((math.sqrt(5) + 1) / 2, x) / math.sqrt(5))


def split_iterable_by_function(iterable: tuple, function) -> tuple:
    seperate_indices = tuple(idx + 1 for idx, v in enumerate(iterable) if function(v))
    if seperate_indices:
        size = len(iterable)
        zip0 = (0,) + seperate_indices
        zip1 = seperate_indices + (
            (size,) if seperate_indices[-1] != size else tuple([])
        )
        return type(iterable)(iterable[i:j] for i, j in zip(zip0, zip1))
    else:
        return type(iterable)((tuple(iterable),))


def split_iterable_by_n(iterable: tuple, n) -> tuple:
    return split_iterable_by_function(iterable, lambda x: x == n)
