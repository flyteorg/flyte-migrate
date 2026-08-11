"""Type transformer bridging v1 ``StructuredDataset`` to v2 ``flyte.io.DataFrame``.

Without this, v2's TypeEngine pickles v1 ``StructuredDataset`` objects, shipping the
producing container's local state instead of a structured-dataset literal.  The
transformer delegates all real I/O to v2's ``DataFrame`` transformer, and hands the
consumer a v1-interface object whose ``open()``/``all()``/``iter()`` route through the
wrapped v2 ``DataFrame`` (the v1 implementations need a v1 FlyteContext that does not
exist inside a v2 container).

Not carried over (v2 limitations of this shim): column-subset projection from
``Annotated[StructuredDataset, kwtypes(...)]`` annotations, and custom metadata.
"""

import inspect
from typing import Any, Optional, Type

from flyte.io import DataFrame
from flyte.types import TypeEngine, TypeTransformer, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from flytekit.types.structured import StructuredDataset


def _df_transformer() -> TypeTransformer[DataFrame]:
    return TypeEngine.get_transformer(DataFrame)


async def _maybe_await(value: Any) -> Any:
    """Await syncify-wrapped results only when they actually come back as awaitables."""
    if inspect.isawaitable(value):
        return await value
    return value


def _resolve_sync(value: Any) -> Any:
    """Unwrap a syncify-wrapped call for a synchronous v1 caller.

    syncify-wrapped v2 methods (``DataFrame.all``, ``from_df``, ...) return the value
    when the calling thread has no event loop, but a coroutine when one is running —
    which is the case for sync v1 task functions executed via v2's run_sync_with_loop.
    Same mechanism as ``_SyncLazyEntity`` in :mod:`flyte_migrate._reference`.
    """
    if inspect.iscoroutine(value):
        from flyte.syncify import syncify

        return syncify._bg_loop.call_in_loop_sync(value)
    return value


class _StructuredDatasetShim(StructuredDataset):
    """v1-interface ``StructuredDataset`` backed by a v2 ``DataFrame`` for I/O."""

    def __init__(self, df2: DataFrame) -> None:
        super().__init__(uri=df2.uri)
        self._df2 = df2

    def open(self, dataframe_type: Type) -> "_StructuredDatasetShim":
        self._df2.open(dataframe_type)
        return self

    def all(self) -> Any:
        return _resolve_sync(self._df2.all())

    def iter(self) -> Any:
        return _resolve_sync(self._df2.iter())


class StructuredDatasetTransformer(TypeTransformer[StructuredDataset]):
    """Bridges v1 ``StructuredDataset`` values across task boundaries on v2."""

    def __init__(self) -> None:
        super().__init__(name="v1 StructuredDataset", t=StructuredDataset)

    def get_literal_type(self, t: Type[StructuredDataset]) -> types_pb2.LiteralType:
        return _df_transformer().get_literal_type(DataFrame)

    def guess_python_type(self, literal_type: types_pb2.LiteralType) -> Type[StructuredDataset]:
        # Let v2's own DataFrame transformer own the reverse mapping.
        raise ValueError(f"Use flyte.io.DataFrame for {literal_type}")

    async def to_literal(
        self,
        python_val: Any,
        python_type: Type[StructuredDataset],
        expected: types_pb2.LiteralType,
    ) -> literals_pb2.Literal:
        if isinstance(python_val, DataFrame):
            df2 = python_val
        elif isinstance(python_val, StructuredDataset):
            if python_val.dataframe is not None:
                df2 = await _maybe_await(DataFrame.from_df(val=python_val.dataframe, uri=python_val.uri))
            elif python_val.uri:
                df2 = DataFrame.from_existing_remote(python_val.uri)
            else:
                raise TypeTransformerFailedError("StructuredDataset has neither a dataframe nor a uri")
        else:
            # v1 lets a task annotated `-> StructuredDataset` return the raw dataframe.
            df2 = await _maybe_await(DataFrame.from_df(val=python_val))
        return await _df_transformer().to_literal(df2, DataFrame, expected)

    async def to_python_value(
        self,
        lv: literals_pb2.Literal,
        expected_python_type: Type[StructuredDataset],
    ) -> Optional[StructuredDataset]:
        df2 = await _df_transformer().to_python_value(lv, DataFrame)
        if df2 is None:
            return None
        return _StructuredDatasetShim(df2)


TypeEngine.register(StructuredDatasetTransformer())
