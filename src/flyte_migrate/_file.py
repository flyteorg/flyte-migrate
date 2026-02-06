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
from fsspec.utils import get_protocol
from mashumaro.types import SerializableType
from pydantic import BaseModel, model_validator

T = typing.TypeVar("T")


def CreateV2File(file: Optional[File[T]] = None, **kwargs) -> File[T]:
    if isinstance(file, File):
        return file
    path = kwargs.get("path")
    if path is None:
        raise ValueError(f"File not found: {path}")

    if get_protocol(path) == "file":
        local_path = path
        remote_path = kwargs.get("remote_path", None)
        return File.from_local_sync(local_path=local_path, remote_destination=remote_path)
    else:
        remote_path = path
        return File.from_existing_remote(remote_path=remote_path)


class FlyteFileV1ToV2(BaseModel, Generic[T], SerializableType):
    file: File

    def _serialize(self) -> Dict[str, Optional[str]]:
        return self.file.model_dump()

    @classmethod
    def _deserialize(cls, file_dump: Dict[str, Optional[str]]) -> "FlyteFileV1ToV2":
        file: File = File.model_validate(file_dump)
        return cls(file=CreateV2File(file))

    @model_validator(mode="before")
    @classmethod
    def pre_init(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if "file" not in data or data["file"] is None:
            file_field_candidates = {key: value for key, value in data.items() if key not in {"file"}}

            if file_field_candidates:
                for k in file_field_candidates.keys():
                    data.pop(k)

                data["file"] = CreateV2File(**file_field_candidates)
        return data

    @classmethod
    def from_source(cls, source: str | os.PathLike) -> "FlyteFileV1ToV2":
        if isinstance(source, os.PathLike):
            path = str(source)
        else:
            path = source
        python_val: File = File.from_existing_remote(path)
        return cls(file=python_val)

    @classmethod
    def new_remote_file(
        cls, file_name: Optional[str] = None, hash_method: Optional[HashMethod | str] = None, **kwargs
    ) -> "FlyteFileV1ToV2":
        file: File = File.new_remote(file_name=file_name, hash_method=hash_method)
        return cls(file=file)

    @classmethod
    def extension(cls) -> str:
        return ""

    def __class_getitem__(cls, item: Any) -> typing.Type["FlyteFileV1ToV2"]:
        from flytekit.types.file import FileExt

        if item is None:
            return cls

        item_string = FileExt.check_and_convert_to_str(item)

        item_string = item_string.strip().lstrip("~").lstrip(".")
        if item == "":
            return cls

        class _SpecificFormatClass(FlyteFileV1ToV2):
            __origin__ = FlyteFileV1ToV2

            class AttributeHider:
                def __get__(self, instance, owner):
                    raise AttributeError(
                        """We have to return false in hasattr(cls, "__class_getitem__")
                         to make mashumaro deserialize FlyteFile correctly."""
                    )

            __class_getitem__ = AttributeHider()  # type: ignore

            @classmethod
            def extension(cls) -> str:
                return item_string

        return _SpecificFormatClass

    @classmethod
    def new(cls, filename: str | os.PathLike) -> "FlyteFileV1ToV2":
        if isinstance(filename, os.PathLike):
            local_path = Path(filename)
        file: File = File.from_local_sync(local_path=local_path)
        return cls(file=file)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_download = False
        self._local_path = ""

    def download(self) -> str:
        return self.__fspath__()

    def __fspath__(self) -> str:
        if not self._is_download:
            self._local_path = self.file.download_sync()
            self._is_download = True
        return self._local_path

    @contextmanager
    def open(
        self,
        *args,
        **kwargs,
    ) -> Generator[IO[Any], None, None]:
        with self.file.open_sync(*args, **kwargs) as f:
            yield f

    @property
    def downloaded(self) -> bool:
        return self._is_download

    @property
    def remote_path(self) -> typing.Optional[os.PathLike]:
        return Path(self.path) if self.path else None

    @property
    def remote_source(self) -> str:
        return self.path

    def __eq__(self, other):
        if isinstance(other, FlyteFileV1ToV2):
            return (
                self.path == other.path
                and self.remote_path == other.remote_path
                and self.extension() == other.extension()
            )
        else:
            return self.path == other

    def __repr__(self):
        return self.path

    def __str__(self):
        return self.path

    def __hash__(self):
        return hash(str(self.path))

    @property
    def path(self) -> str:
        return self.file.path

    @property
    def name(self) -> Optional[str]:
        return self.file.name

    @property
    def format(self) -> str:
        return self.file.format

    @property
    def hash(self) -> Optional[str]:
        return self.file.hash

    @property
    def hash_method(self):
        return self.file.hash_method


class FlyteFilev1Tov2Transformer(TypeTransformer[FlyteFileV1ToV2]):
    def __init__(self):
        super().__init__(name="FlyteFileV1ToV2", t=FlyteFileV1ToV2)

    def get_literal_type(self, t: typing.Type[FlyteFileV1ToV2]) -> types_pb2.LiteralType:
        return types_pb2.LiteralType(
            blob=types_pb2.BlobType(
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
        if (
            literal_type.HasField("blob")
            and literal_type.blob.dimensionality == types_pb2.BlobType.BlobDimensionality.SINGLE
            and literal_type.blob.format != "PythonPickle"  # see pickle transformer
        ):
            return FlyteFileV1ToV2
        raise ValueError(f"Cannot guess python type from {literal_type}")


flytekit.FlyteFile = FlyteFileV1ToV2
TypeEngine.register(FlyteFilev1Tov2Transformer())
