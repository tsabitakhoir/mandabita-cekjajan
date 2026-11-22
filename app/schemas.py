from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

BARCODE = r"^[0-9]{8,14}$"


class NutritionFacts(BaseModel):
    takaran_saji: float = Field(ge=0.1, le=100000)
    satuan_takaran: Literal["g", "ml"]
    sajian_per_kemasan: Optional[float] = Field(default=None, ge=0, le=100000)
    gula_g: float = Field(ge=0, le=100000)
    natrium_mg: float = Field(ge=0, le=10000000)
    lemak_g: float = Field(ge=0, le=100000)


class RegisterRequest(BaseModel):
    nama: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class ChildInput(BaseModel):
    nama_panggilan: str = Field(min_length=1, max_length=50)
    usia_tahun: int = Field(ge=4, le=12)


class ProductInput(BaseModel):
    barcode: Optional[str] = Field(default=None, pattern=BARCODE)
    nama: str = Field(min_length=1, max_length=150)
    merek: Optional[str] = Field(default=None, max_length=100)
    kategori: Literal["makanan", "minuman"]
    nutrisi: NutritionFacts


class AssessmentRequest(BaseModel):
    barcode: Optional[str] = Field(default=None, pattern=BARCODE)
    nutrisi: Optional[NutritionFacts] = None
    jumlah_sajian: float = Field(default=1, ge=0.1, le=100)
    child_id: Optional[str] = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _salah_satu(self):
        if (self.barcode is None) == (self.nutrisi is None):
            raise ValueError("Isi salah satu: barcode atau nutrisi.")
        return self


class ConsumptionInput(BaseModel):
    product_id: str = Field(max_length=64)
    jumlah_sajian: float = Field(default=1, ge=0.1, le=100)
    waktu_konsumsi: Optional[datetime] = None
