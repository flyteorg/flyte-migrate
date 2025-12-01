import os
import typing
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Dict, Generator, Generic, Optional

import flytekit
from flyte.io import File
from flyte.io._hashing_io import HashMethod
from flyte.types import TypeEngine, TypeTransformer, TypeTransformerFailedError
from flyteidl2.core import literals_pb2, types_pb2
from mashumaro.types import SerializableType
from pydantic import BaseModel, model_validator


def noop(): ...


T = typing.TypeVar("T")


def CreateV2File(file: Optional[File] = None, **kwargs) -> File:
    if isinstance(file, File):
        return file
    else:
        return File(**kwargs)


class FlyteFileV1ToV2(BaseModel, Generic[T], SerializableType):
    file: File = None
    is_download: bool = False
    local_path: str = ""

    def _serialize(self) -> Dict[str, Optional[str]]:
        pyd_dump = self.model_dump()
        return pyd_dump

    @classmethod
    def _deserialize(cls, file_dump: Dict[str, Optional[str]]) -> "FlyteFileV1ToV2":
        return FlyteFileV1ToV2.model_validate(file_dump)

    @model_validator(mode="before")
    @classmethod
    def pre_init(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if "file" not in data or data["file"] is None:
            file_field_candidates = {
                key: value for key, value in data.items() if key not in {"file", "is_download", "local_path"}
            }

            if file_field_candidates:
                for k in file_field_candidates.keys():
                    data.pop(k)

                data["file"] = CreateV2File(**file_field_candidates)
        return data

    @classmethod
    def from_source(cls, source: str | os.PathLike) -> "FlyteFileV1ToV2":
        python_val = File.from_existing_remote(source)
        return cls(file=python_val.model_dump())

    @classmethod
    def new_remote_file(
        cls, file_name: Optional[str | os.PathLike] = None, hash_method: Optional[HashMethod | str] = None, **kwargs
    ) -> "FlyteFileV1ToV2":
        file = File.new_remote(file_name=file_name, hash_method=hash_method)
        return cls(file=file.model_dump())

    @classmethod
    def new(cls, filename: str | os.PathLike) -> "FlyteFileV1ToV2":
        return cls(file=File(path=filename).model_dump())

    def download(self) -> str:
        return self.__fspath__()

    def __fspath__(self) -> str:
        if not self.is_download:
            self.local_path = self.file.download_sync()
            self.is_download = True
        return self.local_path

    @contextmanager
    def open(
        self,
        *args,
        **kwargs,
    ) -> Generator[IO[Any], None, None]:
        with self.file.open_sync(*args, **kwargs) as f:
            yield f

    @property
    def path(self) -> str:
        return self.file.path

    @property
    def name(self) -> str:
        return self.file.name

    @property
    def format(self) -> str:
        return self.file.format

    @property
    def hash(self) -> str:
        return self.file.hash

    @property
    def hash_method(self):
        return self.file.hash_method


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
        v2_file = python_val.file
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
            file=CreateV2File(path=uri, name=filename, format=lv.scalar.blob.metadata.type.format, hash=hash_value)
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
