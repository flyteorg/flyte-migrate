"""Tests for the conditional_wf example — verifies task logic and workflow branching."""

import flyte_migrate  # noqa: F401 — triggers patching
from examples.conditional_wf import add, classify, conditional_wf, double, negate, square


class TestClassify:
    def test_positive(self):
        assert classify(x=10) == "positive"

    def test_negative(self):
        assert classify(x=-5) == "negative"

    def test_zero(self):
        assert classify(x=0) == "zero"


class TestDouble:
    def test_positive(self):
        assert double(x=5) == 10

    def test_negative(self):
        assert double(x=-3) == -6

    def test_zero(self):
        assert double(x=0) == 0


class TestNegate:
    def test_positive(self):
        assert negate(x=5) == -5

    def test_negative(self):
        assert negate(x=-3) == 3

    def test_zero(self):
        assert negate(x=0) == 0


class TestSquare:
    def test_positive(self):
        assert square(x=5) == 25

    def test_negative(self):
        assert square(x=-3) == 9

    def test_zero(self):
        assert square(x=0) == 0


class TestAdd:
    def test_basic(self):
        assert add(a=3, b=7) == 10

    def test_negative(self):
        assert add(a=-2, b=5) == 3


class TestConditionalWorkflow:
    def test_positive_branch(self):
        # x=10: classify -> "positive", double(10)=20, add(20, 10)=30
        assert conditional_wf(x=10) == 30

    def test_negative_branch(self):
        # x=-5: classify -> "negative", negate(-5)=5, add(5, -5)=0
        assert conditional_wf(x=-5) == 0

    def test_zero_branch(self):
        # x=0: classify -> "zero", square(0)=0
        assert conditional_wf(x=0) == 0

    def test_positive_one(self):
        # x=1: classify -> "positive", double(1)=2, add(2, 1)=3
        assert conditional_wf(x=1) == 3

    def test_negative_one(self):
        # x=-1: classify -> "negative", negate(-1)=1, add(1, -1)=0
        assert conditional_wf(x=-1) == 0
