"""Tests for the v1 FlyteDirectory -> v2 multipart blob type transformer."""

import os
from pathlib import Path

import pytest
from flyte.io import Dir
from flyte.types import TypeEngine, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from flytekit.types.directory import FlyteDirectory

import flyte_migrate  # noqa: F401 — triggers patching and transformer registration
from flyte_migrate._directory import FlyteDirectoryTransformer

MULTIPART = types_pb2.BlobType.BlobDimensionality.MULTIPART


def _blob_literal(uri: str, fmt: str = "") -> literals_pb2.Literal:
    return literals_pb2.Literal(
        scalar=literals_pb2.Scalar(
            blob=literals_pb2.Blob(
                metadata=literals_pb2.BlobMetadata(type=types_pb2.BlobType(format=fmt, dimensionality=MULTIPART)),
                uri=uri,
            )
        )
    )


class TestRegistration:
    def test_flyte_directory_resolves_to_the_transformer(self):
        assert TypeEngine.get_transformer(FlyteDirectory).name == "v1 FlyteDirectory"

    def test_formatted_subclass_resolves_via_mro(self):
        assert TypeEngine.get_transformer(FlyteDirectory["csv"]).name == "v1 FlyteDirectory"


class TestLiteralType:
    def test_unformatted(self):
        lt = TypeEngine.to_literal_type(FlyteDirectory)
        assert lt.blob.dimensionality == MULTIPART
        assert lt.blob.format == ""

    def test_format_from_annotation(self):
        assert TypeEngine.to_literal_type(FlyteDirectory["csv"]).blob.format == "csv"


class TestToLiteral:
    @pytest.mark.asyncio
    async def test_remote_path_passes_through_without_upload(self):
        lit = await FlyteDirectoryTransformer().to_literal(
            FlyteDirectory(path="s3://bucket/dir"), FlyteDirectory, types_pb2.LiteralType()
        )
        assert lit.scalar.blob.uri == "s3://bucket/dir"
        assert lit.scalar.blob.metadata.type.dimensionality == MULTIPART

    @pytest.mark.asyncio
    async def test_remote_directory_false_means_do_not_upload(self, tmp_path):
        lit = await FlyteDirectoryTransformer().to_literal(
            FlyteDirectory(path=str(tmp_path), remote_directory=False), FlyteDirectory, types_pb2.LiteralType()
        )
        assert lit.scalar.blob.uri == str(tmp_path)

    @pytest.mark.asyncio
    async def test_deferred_upload_is_awaited(self, tmp_path, monkeypatch):
        async def _uploader():
            return "md5", "s3://bucket/uploaded-dir"

        async def _from_local(path, remote_destination=None, **kwargs):
            d = Dir(path=str(path))
            d.lazy_uploader = _uploader
            return d

        monkeypatch.setattr(Dir, "from_local", _from_local)
        lit = await FlyteDirectoryTransformer().to_literal(
            FlyteDirectory(path=str(tmp_path)), FlyteDirectory, types_pb2.LiteralType()
        )
        assert lit.scalar.blob.uri == "s3://bucket/uploaded-dir"

    @pytest.mark.asyncio
    async def test_non_path_value_rejected(self):
        with pytest.raises(TypeTransformerFailedError):
            await FlyteDirectoryTransformer().to_literal(42, FlyteDirectory, types_pb2.LiteralType())  # type: ignore[arg-type]


class TestToPythonValue:
    @pytest.mark.asyncio
    async def test_local_uri_returned_as_is(self, tmp_path):
        fd = await FlyteDirectoryTransformer().to_python_value(_blob_literal(str(tmp_path)), FlyteDirectory)
        assert isinstance(fd, FlyteDirectory)
        assert Path(os.fspath(fd)) == tmp_path

    @pytest.mark.asyncio
    async def test_non_blob_literal_rejected(self):
        scalar = literals_pb2.Literal(scalar=literals_pb2.Scalar(primitive=literals_pb2.Primitive(integer=1)))
        with pytest.raises(TypeTransformerFailedError):
            await FlyteDirectoryTransformer().to_python_value(scalar, FlyteDirectory)


class TestGuessPythonType:
    def test_multipart_blob(self):
        lt = types_pb2.LiteralType(blob=types_pb2.BlobType(format="", dimensionality=MULTIPART))
        assert FlyteDirectoryTransformer().guess_python_type(lt) is FlyteDirectory

    def test_non_blob_rejected(self):
        with pytest.raises(ValueError):
            FlyteDirectoryTransformer().guess_python_type(types_pb2.LiteralType(simple=types_pb2.SimpleType.INTEGER))
