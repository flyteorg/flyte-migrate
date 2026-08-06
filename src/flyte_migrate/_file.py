"""Type transformer bridging v1 ``flytekit.types.file.FlyteFile`` to v2 blob literals.

v2's TypeEngine has no transformer for the v1 type, so it falls back to pickling the
``FlyteFile`` object. That ships the *producing* container's local path and nothing
else, and the consumer then fails with ``File /tmp/... does not exist``.

This transformer restores v1 semantics: the file is uploaded to blob storage on the way
out and downloaded to a local path on the way in, so v1 code that does ``open(ff)`` keeps
working. Both directions go through v2's ``flyte.io.File``, which owns the actual I/O.
"""

from typing import Optional, Type, Union

from flyte.io import File
from flyte.types import TypeEngine, TypeTransformer, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from flytekit.types.file import FlyteFile
from fsspec.utils import get_protocol


def _is_remote(path: str) -> bool:
    return get_protocol(path) != "file"


def _format_of(t: Type[FlyteFile]) -> str:
    """The blob format for a v1 ``FlyteFile["csv"]``-style annotation ("" when unformatted)."""
    extension = getattr(t, "extension", None)
    return extension() if callable(extension) else ""


class FlyteFileTransformer(TypeTransformer[FlyteFile]):
    """Uploads/downloads v1 ``FlyteFile`` values so they survive a task boundary on v2."""

    def __init__(self) -> None:
        super().__init__(name="v1 FlyteFile", t=FlyteFile)

    def get_literal_type(self, t: Type[FlyteFile]) -> types_pb2.LiteralType:
        return types_pb2.LiteralType(
            blob=types_pb2.BlobType(
                format=_format_of(t),
                dimensionality=types_pb2.BlobType.BlobDimensionality.SINGLE,
            )
        )

    def guess_python_type(self, literal_type: types_pb2.LiteralType) -> Type[FlyteFile]:
        if literal_type.HasField("blob") and (
            literal_type.blob.dimensionality == types_pb2.BlobType.BlobDimensionality.SINGLE
        ):
            return FlyteFile
        raise ValueError(f"Cannot convert {literal_type} to FlyteFile")

    async def to_literal(
        self,
        python_val: Union[FlyteFile, str],
        python_type: Type[FlyteFile],
        expected: types_pb2.LiteralType,
    ) -> literals_pb2.Literal:
        # A file we downloaded in to_python_value is already in blob storage — forward the
        # blob instead of re-uploading. The parent workflow serializes a child's inputs off
        # the controller thread, where there is no task context to upload from, so this is
        # the only thing that keeps a forwarded file addressable by the next task.
        remote_source = getattr(python_val, "_remote_source", None)
        if remote_source:
            return self._blob(str(remote_source), python_type)

        # v1 lets a task annotated `-> FlyteFile` return a bare path string.
        source = python_val.path if isinstance(python_val, FlyteFile) else python_val
        if not isinstance(source, (str, bytes)) and not hasattr(source, "__fspath__"):
            raise TypeTransformerFailedError(f"Expected a FlyteFile or path, received {type(python_val)}")
        source = str(source)

        if _is_remote(source):
            uri = source
        else:
            # remote_path=False means "already where it should be, do not upload".
            remote_path = getattr(python_val, "_remote_path", None) if isinstance(python_val, FlyteFile) else None
            if remote_path is False:
                uri = source
            else:
                # Always hand from_local an explicit destination. Left to choose for itself it
                # may skip the upload and return the local path — which is what happens when a
                # parent workflow forwards a child's output, and the consumer then gets a path
                # that only existed in the parent's container.
                uploaded: File = await File.from_local(source, remote_destination=remote_path or None)
                # from_local can defer the upload; reading .path without running the uploader
                # would ship this container's local path and nothing else.
                uri = (await uploaded.lazy_uploader())[1] if uploaded.lazy_uploader else uploaded.path
        return self._blob(uri, python_type)

    @staticmethod
    def _blob(uri: str, python_type: Type[FlyteFile]) -> literals_pb2.Literal:
        return literals_pb2.Literal(
            scalar=literals_pb2.Scalar(
                blob=literals_pb2.Blob(
                    metadata=literals_pb2.BlobMetadata(
                        type=types_pb2.BlobType(
                            format=_format_of(python_type),
                            dimensionality=types_pb2.BlobType.BlobDimensionality.SINGLE,
                        )
                    ),
                    uri=uri,
                )
            )
        )

    async def to_python_value(
        self,
        lv: literals_pb2.Literal,
        expected_python_type: Type[FlyteFile],
    ) -> Optional[FlyteFile]:
        if not lv.scalar.HasField("blob"):
            raise TypeTransformerFailedError(f"Expected blob literal, received {lv}")

        uri = lv.scalar.blob.uri
        if not _is_remote(uri):
            return expected_python_type(path=uri)

        # ponytail: eager download. v1 defers until open(), but that downloader needs a v1
        # FlyteContext that does not exist inside a v2 container. Make it lazy only if
        # tasks start taking large files they never read.
        local_path = await File.from_existing_remote(uri).download()
        downloaded = expected_python_type(path=local_path, remote_path=False)
        # Remember where it came from so forwarding it does not need to re-upload.
        downloaded._remote_source = uri
        return downloaded


TypeEngine.register(FlyteFileTransformer())
