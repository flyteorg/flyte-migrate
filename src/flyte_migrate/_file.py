import os
import typing
from pathlib import Path

import flytekit
from flyte.io import File
from flyte.types import TypeEngine, TypeTransformer, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from typing import Optional, Generator, IO, Any
from contextlib import contextmanager
from flyte.io._hashing_io import HashMethod

def noop(): ...


T = typing.TypeVar("T")


class FlyteFileV1ToV2():
    _file: Optional[File] = None
    is_download: bool = False
    local_path: str = ""

    @classmethod
    def from_source(cls, source: str | os.PathLike) -> "FlyteFileV1ToV2":
        python_val = File.from_existing_remote(source)
        return cls(file=python_val)
    
    @classmethod
    def new_remote_file(cls, hash_method: Optional[HashMethod | str] = None, **kwargs) -> "FlyteFileV1ToV2":
        return cls(file=File.new_remote(hash_method=hash_method))

    def __init__(
        self,
        file: Optional[File] = None,
        **kwargs
    ):
        if file:
            self._file = file
        else:
            f = File(**kwargs)
            self._file = f
    
    @classmethod
    def new(cls, filename: str | os.PathLike) -> "FlyteFileV1ToV2":
        return cls(file=File(path=filename))
    
    def download(self) -> str:
        return self.__fspath__()
    
    def __fspath__(self) -> str:
        if not self.is_download:
            self.local_path = self._file.download_sync()
            self.is_download = True
        return self.local_path
    
    @contextmanager
    def open(
        self,
        *args,
        **kwargs,
    ) -> Generator[IO[Any], None, None]:
        with self._file.open_sync(*args, **kwargs) as f:
            yield f
    
    @property
    def path(self) -> str:
        return self._file.path

    @property
    def name(self) -> str:
        return self._file.name
    
    @property
    def format(self) -> str:
        return self._file.format
    
    @property
    def hash(self) -> str:
        return self._file.hash
    
    @property
    def hash_method(self):
        return self._file.hash_method


class FlyteFilev1Tov2Transformer(TypeTransformer[FlyteFileV1ToV2]):
    """
    Transformer for File objects. This type transformer does not handle any i/o. That is now the responsibility of the
    user.
    """

    def __init__(self):
        super().__init__(name="FlyteFileV1ToV2", t=FlyteFileV1ToV2)

    def get_literal_type(self, t: typing.Type[FlyteFileV1ToV2]) -> types_pb2.LiteralType:
        """Get the Flyte literal type for a File type."""
        return types_pb2.LiteralType(
            blob=types_pb2.BlobType(
                # todo: set format from generic
                format="",  # Format is determined by the generic type T
                dimensionality=types_pb2.BlobType.BlobDimensionality.SINGLE,
            )
        )

    async def to_literal(
        self,
        python_val: FlyteFileV1ToV2,
        python_type: typing.Type[FlyteFileV1ToV2],
        expected: types_pb2.LiteralType,
    ) -> literals_pb2.Literal:
        """Convert a File object to a Flyte literal."""
        if not isinstance(python_val, FlyteFileV1ToV2):
            raise TypeTransformerFailedError(f"Expected File object, received {type(python_val)}")
        v2_file = python_val._file
        # Get flyte File to python_val
        return literals_pb2.Literal(
            scalar=literals_pb2.Scalar(
                blob=literals_pb2.Blob(
                    metadata=literals_pb2.BlobMetadata(
                        type=types_pb2.BlobType(
                            format=v2_file.format, dimensionality=types_pb2.BlobType.BlobDimensionality.SINGLE
                        )
                    ),
                    uri=v2_file.path,
                )
            ),
            hash=v2_file.hash if v2_file.hash else None,
        )

    async def to_python_value(
        self,
        lv: literals_pb2.Literal,
        expected_python_type: typing.Type[FlyteFileV1ToV2],
    ) -> FlyteFileV1ToV2:
        """Convert a Flyte literal to a File object."""
        if not lv.scalar.HasField("blob"):
            raise TypeTransformerFailedError(f"Expected blob literal, received {lv}")
        if not lv.scalar.blob.metadata.type.dimensionality == types_pb2.BlobType.BlobDimensionality.SINGLE:
            raise TypeTransformerFailedError(
                f"Expected single part blob, received {lv.scalar.blob.metadata.type.dimensionality}"
            )

        uri = lv.scalar.blob.uri
        filename = Path(uri).name
        hash_value = lv.hash if lv.hash else None
        f: FlyteFileV1ToV2 = FlyteFileV1ToV2(
            path=uri, name=filename, format=lv.scalar.blob.metadata.type.format, hash=hash_value
        )
        return f

    def guess_python_type(self, literal_type: types_pb2.LiteralType) -> typing.Type[FlyteFileV1ToV2]:
        """Guess the Python type from a Flyte literal type."""
        if (
            literal_type.HasField("blob")
            and literal_type.blob.dimensionality == types_pb2.BlobType.BlobDimensionality.SINGLE
            and literal_type.blob.format != "PythonPickle"  # see pickle transformer
        ):
            return FlyteFileV1ToV2
        raise ValueError(f"Cannot guess python type from {literal_type}")


flytekit.FlyteFile = FlyteFileV1ToV2
TypeEngine.register(FlyteFilev1Tov2Transformer())
