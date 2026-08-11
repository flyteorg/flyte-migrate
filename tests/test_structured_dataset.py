"""Tests for the v1 StructuredDataset -> v2 flyte.io.DataFrame type transformer."""

import pytest
from flyte.io import DataFrame
from flyte.types import TypeEngine, TypeTransformerFailedError
from flytekit.types.structured import StructuredDataset

import flyte_migrate  # noqa: F401 — triggers patching and transformer registration
from flyte_migrate._structured_dataset import StructuredDatasetTransformer, _StructuredDatasetShim


class TestRegistration:
    def test_structured_dataset_resolves_to_the_transformer(self):
        assert TypeEngine.get_transformer(StructuredDataset).name == "v1 StructuredDataset"

    def test_literal_type_is_structured_dataset(self):
        lt = TypeEngine.to_literal_type(StructuredDataset)
        assert lt.HasField("structured_dataset_type")


class TestToLiteral:
    @pytest.mark.asyncio
    async def test_uri_only_sd_passes_through(self):
        t = StructuredDatasetTransformer()
        lt = t.get_literal_type(StructuredDataset)
        lit = await t.to_literal(StructuredDataset(uri="s3://bucket/data"), StructuredDataset, lt)
        assert lit.scalar.structured_dataset.uri == "s3://bucket/data"

    @pytest.mark.asyncio
    async def test_dataframe_value_goes_through_from_df(self, monkeypatch):
        """A v1 SD wrapping an in-memory dataframe must be handed to v2 DataFrame.from_df."""
        seen = {}

        def _from_df(val=None, uri=None):
            seen["val"], seen["uri"] = val, uri
            return DataFrame(uri="s3://bucket/uploaded")

        monkeypatch.setattr(DataFrame, "from_df", _from_df)
        t = StructuredDatasetTransformer()
        lt = t.get_literal_type(StructuredDataset)
        sd = StructuredDataset(dataframe={"col": [1, 2]}, uri="s3://bucket/dest")
        lit = await t.to_literal(sd, StructuredDataset, lt)
        assert seen == {"val": {"col": [1, 2]}, "uri": "s3://bucket/dest"}
        assert lit.scalar.structured_dataset.uri == "s3://bucket/uploaded"

    @pytest.mark.asyncio
    async def test_raw_dataframe_return_value_accepted(self, monkeypatch):
        """v1 lets a task annotated `-> StructuredDataset` return the bare dataframe."""

        def _from_df(val=None, uri=None):
            return DataFrame(uri="s3://bucket/raw")

        monkeypatch.setattr(DataFrame, "from_df", _from_df)
        t = StructuredDatasetTransformer()
        lit = await t.to_literal({"col": [1]}, StructuredDataset, t.get_literal_type(StructuredDataset))
        assert lit.scalar.structured_dataset.uri == "s3://bucket/raw"

    @pytest.mark.asyncio
    async def test_empty_sd_rejected(self):
        t = StructuredDatasetTransformer()
        with pytest.raises(TypeTransformerFailedError):
            await t.to_literal(StructuredDataset(), StructuredDataset, t.get_literal_type(StructuredDataset))


class TestToPythonValue:
    @pytest.mark.asyncio
    async def test_round_trip_returns_v1_interface_shim(self):
        t = StructuredDatasetTransformer()
        lt = t.get_literal_type(StructuredDataset)
        lit = await t.to_literal(StructuredDataset(uri="s3://bucket/data"), StructuredDataset, lt)
        sd = await t.to_python_value(lit, StructuredDataset)
        assert isinstance(sd, StructuredDataset)
        assert isinstance(sd, _StructuredDatasetShim)
        assert sd.uri == "s3://bucket/data"

    @pytest.mark.asyncio
    async def test_open_records_type_and_chains(self):
        t = StructuredDatasetTransformer()
        lt = t.get_literal_type(StructuredDataset)
        lit = await t.to_literal(StructuredDataset(uri="s3://bucket/data"), StructuredDataset, lt)
        sd = await t.to_python_value(lit, StructuredDataset)
        assert sd.open(dict) is sd
        assert sd._df2._dataframe_type is dict
