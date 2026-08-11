"""Type transformer bridging v1 ``flytekit.types.directory.FlyteDirectory`` to v2 blob literals.

Same story as :mod:`flyte_migrate._file`: v2's TypeEngine has no transformer for the v1
type, so it falls back to pickling the ``FlyteDirectory`` object — shipping the producing
container's local path and nothing else. This transformer uploads the directory to blob
storage on the way out and downloads it on the way in, via v2's ``flyte.io.Dir``.
"""

from typing import Optional, Type, Union

from flyte.io import Dir
from flyte.types import TypeEngine, TypeTransformer, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from flytekit.types.directory import FlyteDirectory
from fsspec.utils import get_protocol


def _is_remote(path: str) -> bool:
    return get_protocol(path) != "file"


def _format_of(t: Type[FlyteDirectory]) -> str:
    """The blob format for a v1 ``FlyteDirectory["csv"]``-style annotation ("" when unformatted)."""
    extension = getattr(t, "extension", None)
    return extension() if callable(extension) else ""


class FlyteDirectoryTransformer(TypeTransformer[FlyteDirectory]):
    """Uploads/downloads v1 ``FlyteDirectory`` values so they survive a task boundary on v2."""

    def __init__(self) -> None:
        super().__init__(name="v1 FlyteDirectory", t=FlyteDirectory)

    def get_literal_type(self, t: Type[FlyteDirectory]) -> types_pb2.LiteralType:
        return types_pb2.LiteralType(
            blob=types_pb2.BlobType(
                format=_format_of(t),
                dimensionality=types_pb2.BlobType.BlobDimensionality.MULTIPART,
            )
        )

    def guess_python_type(self, literal_type: types_pb2.LiteralType) -> Type[FlyteDirectory]:
        if literal_type.HasField("blob") and (
            literal_type.blob.dimensionality == types_pb2.BlobType.BlobDimensionality.MULTIPART
        ):
            return FlyteDirectory
        raise ValueError(f"Cannot convert {literal_type} to FlyteDirectory")

    async def to_literal(
        self,
        python_val: Union[FlyteDirectory, str],
        python_type: Type[FlyteDirectory],
        expected: types_pb2.LiteralType,
    ) -> literals_pb2.Literal:
        # A directory we downloaded in to_python_value is already in blob storage — forward
        # the blob instead of re-uploading (see _file.py for why this matters when a parent
        # workflow forwards a child's output).
        remote_source = getattr(python_val, "_remote_source", None)
        if remote_source:
            return self._blob(str(remote_source), python_type)

        # v1 lets a task annotated `-> FlyteDirectory` return a bare path string.
        source = python_val.path if isinstance(python_val, FlyteDirectory) else python_val
        if not isinstance(source, (str, bytes)) and not hasattr(source, "__fspath__"):
            raise TypeTransformerFailedError(f"Expected a FlyteDirectory or path, received {type(python_val)}")
        source = str(source)

        if _is_remote(source):
            uri = source
        else:
            # remote_directory=False means "already where it should be, do not upload".
            remote_dir = (
                getattr(python_val, "_remote_directory", None) if isinstance(python_val, FlyteDirectory) else None
            )
            if remote_dir is False:
                uri = source
            else:
                uploaded: Dir = await Dir.from_local(source, remote_destination=remote_dir or None)
                uri = (await uploaded.lazy_uploader())[1] if uploaded.lazy_uploader else uploaded.path
        return self._blob(uri, python_type)

    @staticmethod
    def _blob(uri: str, python_type: Type[FlyteDirectory]) -> literals_pb2.Literal:
        return literals_pb2.Literal(
            scalar=literals_pb2.Scalar(
                blob=literals_pb2.Blob(
                    metadata=literals_pb2.BlobMetadata(
                        type=types_pb2.BlobType(
                            format=_format_of(python_type),
                            dimensionality=types_pb2.BlobType.BlobDimensionality.MULTIPART,
                        )
                    ),
                    uri=uri,
                )
            )
        )

    async def to_python_value(
        self,
        lv: literals_pb2.Literal,
        expected_python_type: Type[FlyteDirectory],
    ) -> Optional[FlyteDirectory]:
        if not lv.scalar.HasField("blob"):
            raise TypeTransformerFailedError(f"Expected blob literal, received {lv}")

        uri = lv.scalar.blob.uri
        if not _is_remote(uri):
            return expected_python_type(path=uri)

        # ponytail: eager download, same trade-off as _file.py — v1's lazy downloader needs
        # a v1 FlyteContext that does not exist inside a v2 container.
        local_path = await Dir.from_existing_remote(uri).download()
        downloaded = expected_python_type(path=local_path, remote_directory=False)
        # Remember where it came from so forwarding it does not need to re-upload.
        downloaded._remote_source = uri
        return downloaded


TypeEngine.register(FlyteDirectoryTransformer())
