from mu.mel import abstract
from fractions import Fraction
import pyprimes
import functools
from typing import get_type_hints


def comparable_bool_decorator(func):
    def wrap(*args, **kwargs):
        if Monzo.is_comparable(args[0], args[1]):
            return func(*args, **kwargs)
        else:
            return False
    return wrap


def comparable_monzo_decorator(func):
    def wrap(*args, **kwargs):
        if Monzo.is_comparable(args[0], args[1]):
            return func(*args, **kwargs)
        else:
            return Monzo([])
    return wrap


class Monzo(tuple):
    val_shift = 0

    def __new__(cls, iterable, *args, **kwargs):
        return tuple.__new__(cls, iterable)

    def __init__(self, iter, val_shift=0):
        self.val_shift = val_shift

    @staticmethod
    def decompose(num: int) -> tuple:
        """written-out prime-number-decomposition"""
        writtenout = ([x] * y for x, y in pyprimes.factorise(num))
        return tuple(functools.reduce(lambda x, y: x + y, writtenout))

    @staticmethod
    def adjusted_monzos(m0, m1) -> tuple:
        m0, m1 = list(m0), list(m1)
        while len(m1) < len(m0):
            m1.append(0)
        while len(m0) < len(m1):
            m0.append(0)
        return tuple(m0), tuple(m1)

    @staticmethod
    def is_comparable(m0: "Monzo", m1: "Monzo") -> bool:
        try:
            return m0.val_shift == m1.val_shift
        except AttributeError:
            return False

    @staticmethod
    def calc_iterables(iterable0, iterable1, operation) -> iter:
        return (operation(x, y) for x, y in zip(iterable0, iterable1))

    @staticmethod
    def adjust_ratio(r: Fraction, val_border=int) -> Fraction:
        if val_border > 1:
            while r > val_border:
                r /= val_border
            while r < 1:
                r *= val_border
            return r
        else:
            return r

    @staticmethod
    def monzo2ratio(monzo: tuple, val: tuple, val_border: int) -> Fraction:
        numerator = 1
        denominator = 1
        for number, exponent in zip(val, monzo):
            if exponent > 0:
                numerator *= pow(number, exponent)
            elif exponent < 0:
                exponent *= -1
                denominator *= pow(number, exponent)
        return Monzo.adjust_ratio(Fraction(numerator, denominator), val_border)

    @staticmethod
    def ratio2monzo(ratio: Fraction, val_shift=0) -> "Monzo":
        gen_pos = pyprimes.factorise(ratio.numerator)
        gen_neg = pyprimes.factorise(ratio.denominator)

        biggest_prime = max(Monzo.decompose(
            ratio.numerator) + Monzo.decompose(ratio.denominator))
        monzo = [0] * pyprimes.prime_count(biggest_prime)

        for num, fac in gen_pos:
            monzo[pyprimes.prime_count(num) - 1] += fac

        for num, fac in gen_neg:
            monzo[pyprimes.prime_count(num) - 1] -= fac

        return Monzo(monzo[val_shift:])

    @property
    def val(self) -> tuple:
        return tuple(pyprimes.nprimes(
            len(self) + self.val_shift))[self.val_shift:]

    @property
    def val_border(self) -> tuple:
        if self.val_shift == 0:
            return 1
        else:
            return tuple(pyprimes.nprimes(
                len(self) + self.val_shift))[self.val_shift - 1]

    @property
    def ratio(self) -> Fraction:
        return Monzo.monzo2ratio(self, self.val, self.val_border)

    @property
    def float(self) -> float:
        return float(self.ratio)

    @property
    def gender(self) -> int:
        maxima = max(self)
        minima = min(self)
        if (maxima > 0 and minima >= 0) or (
                maxima > 0 and self.index(maxima) > self.index(minima)):
                return 1
        elif maxima <= 0 and minima < 0 or (
                minima < 0 and self.index(minima) > self.index(maxima)):
            return -1
        else:
            return 0

    @property
    def harmonic(self) -> int:
        if self.ratio.denominator % 2 == 0:
            return self.ratio.numerator
        elif self.ratio.numerator % 2 == 0:
            return - self.ratio.denominator
        elif self.ratio == Fraction(1, 1):
            return 1
        else:
            return 0

    @property
    def primes(self) -> tuple:
        p = Monzo.decompose(self.ratio.numerator * self.ratio.denominator)
        return tuple(set(p))[self.val_shift:]

    @property
    def wilson(self) -> int:
        num = self.ratio.numerator
        de = self.ratio.denominator
        while num % 2 == 0:
            num /= 2
        while de % 2 == 0:
            de /= 2
        return int(sum(filter(lambda x: x > 1, (num, de))))

    @property
    def vogel(self) -> int:
        num = self.ratio.numerator
        de = self.ratio.denominator
        fac0 = 0
        while num % 2 == 0:
            num /= 2
            fac0 += 1
        while de % 2 == 0:
            de /= 2
            fac0 += 1
        return int(sum(filter(lambda x: x > 1, (num, de))) + fac0)

    @comparable_bool_decorator
    def is_related(self: "Monzo", other: "Monzo") -> bool:
        for p in self.primes:
            if p in other.primes:
                return True
        return False

    @comparable_bool_decorator
    def is_congeneric(self: "Monzo", other: "Monzo") -> bool:
        if self.primes == other.primes:
            return True
        else:
            return False

    @comparable_bool_decorator
    def __eq__(self: "Monzo", other: "Monzo") -> bool:
        return tuple.__eq__(self, other)

    def summed(self) -> int:
        return sum(map(lambda x: abs(x), self))

    def subvert(self) -> list:
        def ispos(num):
            if num > 0:
                return 1
            else:
                return -1
        sep = [tuple(type(self)([0] * counter + [ispos(vec)])
                     for i in range(abs(vec)))
               for counter, vec in enumerate(self) if vec != 0]
        res = [a for sub in sep for a in sub]
        if len(res) == 0:
            res.append(type(self)([0]))
        return res

    def copy(self) -> "Monzo":
        return Monzo(self, self.val_shift)

    @comparable_monzo_decorator
    def __math(self, other, operation) -> "Monzo":
        m0, m1 = Monzo.adjusted_monzos(self, other)
        return Monzo(Monzo.calc_iterables(m0, m1, operation), self.val_shift)

    def __add__(self, other: "Monzo") -> "Monzo":
        return self.__math(other, lambda x, y: x + y)

    def __sub__(self, other: "Monzo") -> "Monzo":
        return self.__math(other, lambda x, y: x - y)

    def __mul__(self, fac: int) -> "Monzo":
        return self.__math(Monzo([fac] * len(self), val_shift=self.val_shift),
                           lambda x, y: x * y)

    def inverse(self) -> "Monzo":
        return Monzo(list(map(lambda x: -x, self)), self.val_shift)

    def shift(self, shiftval: int) -> "Monzo":
        if shiftval > 0:
            m = [0] * shiftval + list(self)
        else:
            m = self[abs(shiftval):]
        return Monzo(m, self.val_shift)


class JITone(Monzo, abstract.AbstractTone):
    multiply = 1

    def __new__(cls, iterable, *args, **kwargs):
        def is_changeable(method):
            if callable(method):
                try:
                    res = get_type_hints(method)["return"]
                    return res == Monzo
                except KeyError:
                    return False
            else:
                return False

        def adjust_methods(m):
            def decorator(func):
                def wrap(*args, **kwargs):
                    return JITone(func(*args, **kwargs))
                w = wrap
                w.__annotations__.update({"return": type(res)})
                return w
            return tuple((key, decorator(func)) for key, func in m)

        if not iterable:
            iterable = (0,)

        res = Monzo.__new__(cls, iterable)
        keys = tuple(key for key in dir(res) if not abstract.is_private(key))
        methods = tuple(getattr(res, key) for key in keys)
        filtered = ((key, method) for key, method in zip(keys, methods)
                    if is_changeable(method))
        for key, func in adjust_methods(filtered):
            setattr(res, key, func)
        return res

    def __init__(self, iterable, val_shift=0, multiply=1):
        self.val_shift = val_shift
        self.multiply = multiply

    def __eq__(self, other) -> bool:
        return abstract.AbstractTone.__eq__(self, other)

    def __repr__(self) -> str:
        return str(self.ratio)

    @property
    def monzo(self) -> tuple:
        return tuple(self)

    def __add__(self, other) -> "JITone":
        return JITone(Monzo.__add__(self, other))

    def __sub__(self, other) -> "JITone":
        return JITone(Monzo.__sub__(self, other))

    def __mul__(self, other) -> "JITone":
        return JITone(Monzo.__mul__(self, other))

    def __hash__(self):
        return abstract.AbstractTone.__hash__(self)

    def calc(self, factor=1) -> float:
        return float(self.ratio * self.multiply * factor)

    def copy(self) -> "JITone":
        return JITone(self, self.val_shift, self.multiply)

    @classmethod
    def from_ratio(cls, num: int, den: int, multiply=1) -> "JITone":
        obj = cls(JITone.ratio2monzo(Fraction(num, den), cls.val_shift))
        obj.multiply = multiply
        return obj


class JIContainer:
    def __init__(self, iterable, multiply=1):
        super(type(self), self).__init__(iterable)
        self.multiply = multiply
        self.__val_shift = 0

    @classmethod
    def mk_line(cls, reference, count):
        return cls([reference * (counter + 1) for counter in range(count)])

    @classmethod
    def mk_line_and_inverse(cls, reference, count):
        m0 = cls.mk_line(reference, count)
        return m0 & m0.inverse()

    def show(self) -> tuple:
        r = tuple((r, p, round(f, 2))
                  for r, p, f in zip(self, self.primes, self.freq))
        return tuple(sorted(r, key=lambda t: t[2]))

    def set_multiply(self, arg):
        for t in self:
            t.multiply = arg


class JIMel(JITone.mk_iterable(abstract.AbstractMelody), JIContainer):
    def __init__(self, iterable, multiply=1):
        return JIContainer.__init__(self, iterable, multiply)

    def calc(self, factor=1) -> tuple:
        return tuple(t.calc(self.multiply * factor) for t in self)

    @property
    def freq(self) -> tuple:
        return self.calc()

    def __add__(self, other: "JIMel"):
        return JIMel(m0 + m1 for m0, m1 in zip(self, other))

    def __sub__(self, other: "JIMel"):
        return JIMel(m0 - m1 for m0, m1 in zip(self, other))

    @property
    def val_shift(self) -> int:
        return self.__val_shift

    @val_shift.setter
    def val_shift(self, arg) -> None:
        for f in self:
            f.val_shift = arg
        self.__val_shift = arg


class JIHarmony(JITone.mk_iterable(abstract.AbstractHarmony), JIContainer):
    def __init__(self, iterable, multiply=1):
        return JIContainer.__init__(self, iterable, multiply)

    def calc(self, factor=1) -> tuple:
        return tuple(t.calc(self.multiply * factor) for t in self)

    @property
    def freq(self) -> tuple:
        return self.calc()

    @property
    def val_shift(self) -> int:
        return self.__val_shift

    @val_shift.setter
    def val_shift(self, arg) -> None:
        for f in self:
            f.val_shift = arg
        self.__val_shift = arg
