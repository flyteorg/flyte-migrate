"""Tests for the v1 FlyteFile -> v2 blob type transformer."""

import os
from pathlib import Path

import pytest
from flyte.io import File
from flyte.types import TypeEngine, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from flytekit.types.file import FlyteFile

import flyte_migrate  # noqa: F401 — triggers patching and transformer registration
from flyte_migrate._file import FlyteFileTransformer

SINGLE = types_pb2.BlobType.BlobDimensionality.SINGLE


def _blob_literal(uri: str, fmt: str = "") -> literals_pb2.Literal:
    return literals_pb2.Literal(
        scalar=literals_pb2.Scalar(
            blob=literals_pb2.Blob(
                metadata=literals_pb2.BlobMetadata(type=types_pb2.BlobType(format=fmt, dimensionality=SINGLE)),
                uri=uri,
            )
        )
    )


class TestRegistration:
    def test_flyte_file_resolves_to_the_transformer(self):
        assert TypeEngine.get_transformer(FlyteFile).name == "v1 FlyteFile"

    def test_formatted_subclass_resolves_via_mro(self):
        """FlyteFile["csv"] is a generated subclass, so lookup has to walk the MRO."""
        assert TypeEngine.get_transformer(FlyteFile["csv"]).name == "v1 FlyteFile"


class TestLiteralType:
    def test_unformatted(self):
        lt = TypeEngine.to_literal_type(FlyteFile)
        assert lt.blob.dimensionality == SINGLE
        assert lt.blob.format == ""

    def test_format_from_annotation(self):
        assert TypeEngine.to_literal_type(FlyteFile["csv"]).blob.format == "csv"


class TestToLiteral:
    @pytest.mark.asyncio
    async def test_remote_path_passes_through_without_upload(self):
        lit = await FlyteFileTransformer().to_literal(
            FlyteFile(path="s3://bucket/key.txt"), FlyteFile, types_pb2.LiteralType()
        )
        assert lit.scalar.blob.uri == "s3://bucket/key.txt"

    @pytest.mark.asyncio
    async def test_remote_path_false_means_do_not_upload(self, tmp_path):
        local = tmp_path / "already-there.txt"
        local.write_text("x")
        lit = await FlyteFileTransformer().to_literal(
            FlyteFile(path=str(local), remote_path=False), FlyteFile, types_pb2.LiteralType()
        )
        assert lit.scalar.blob.uri == str(local)

    @pytest.mark.asyncio
    async def test_format_recorded_on_the_blob(self):
        lit = await FlyteFileTransformer().to_literal(
            FlyteFile(path="s3://bucket/key.csv"), FlyteFile["csv"], types_pb2.LiteralType()
        )
        assert lit.scalar.blob.metadata.type.format == "csv"

    @pytest.mark.asyncio
    async def test_deferred_upload_is_awaited(self, tmp_path, monkeypatch):
        """from_local defers the upload when there is no raw data path; reading .path skips it."""
        local = tmp_path / "out.txt"
        local.write_text("x")

        async def _uploader():
            return "md5", "s3://bucket/uploaded.txt"

        async def _from_local(path, remote_destination=None, hash_method=None):
            f = File(path=str(path))
            f.lazy_uploader = _uploader
            return f

        monkeypatch.setattr(File, "from_local", _from_local)
        lit = await FlyteFileTransformer().to_literal(FlyteFile(path=str(local)), FlyteFile, types_pb2.LiteralType())
        assert lit.scalar.blob.uri == "s3://bucket/uploaded.txt"

    @pytest.mark.asyncio
    async def test_non_path_value_rejected(self):
        with pytest.raises(TypeTransformerFailedError):
            await FlyteFileTransformer().to_literal(42, FlyteFile, types_pb2.LiteralType())  # type: ignore[arg-type]


class TestToPythonValue:
    @pytest.mark.asyncio
    async def test_local_uri_returned_as_is(self, tmp_path):
        local = tmp_path / "in.txt"
        local.write_text("hello")
        ff = await FlyteFileTransformer().to_python_value(_blob_literal(str(local)), FlyteFile)
        assert isinstance(ff, FlyteFile)
        # os.fspath(ff) is what v1 user code hits via open(ff) — it must be the real local file
        assert Path(os.fspath(ff)) == local

    @pytest.mark.asyncio
    async def test_non_blob_literal_rejected(self):
        scalar = literals_pb2.Literal(scalar=literals_pb2.Scalar(primitive=literals_pb2.Primitive(integer=1)))
        with pytest.raises(TypeTransformerFailedError):
            await FlyteFileTransformer().to_python_value(scalar, FlyteFile)


class TestGuessPythonType:
    def test_single_blob(self):
        lt = types_pb2.LiteralType(blob=types_pb2.BlobType(format="", dimensionality=SINGLE))
        assert FlyteFileTransformer().guess_python_type(lt) is FlyteFile

    def test_non_blob_rejected(self):
        with pytest.raises(ValueError):
            FlyteFileTransformer().guess_python_type(types_pb2.LiteralType(simple=types_pb2.SimpleType.INTEGER))
