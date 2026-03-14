from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, Text, DateTime
from sqlalchemy.orm import relationship

from api.database import Base


class Circuit(Base):
    __tablename__ = "circuits"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    country = Column(Text, nullable=False)
    city = Column(Text, nullable=False)
    circuit_type = Column(Text, nullable=False)
    total_laps = Column(Integer, nullable=False)
    length_km = Column(Numeric(6, 3), nullable=False)

    races = relationship("Race", back_populates="circuit")


class Race(Base):
    __tablename__ = "races"

    id = Column(Integer, primary_key=True)
    season = Column(Integer, nullable=False)
    round = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    circuit_id = Column(Integer, ForeignKey("circuits.id"), nullable=False)
    date = Column(Date, nullable=False)
    is_completed = Column(Boolean, nullable=False, default=False)

    circuit = relationship("Circuit", back_populates="races")
    results = relationship("RaceResult", back_populates="race")
    predictions = relationship("Prediction", back_populates="race")
    evaluation_metrics = relationship("EvaluationMetrics", back_populates="race")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True)
    code = Column(Text, nullable=False, unique=True)
    full_name = Column(Text, nullable=False)
    nationality = Column(Text, nullable=False)


class Constructor(Base):
    __tablename__ = "constructors"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    nationality = Column(Text, nullable=False)
    color_hex = Column(Text, nullable=False)


class RaceResult(Base):
    __tablename__ = "race_results"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    constructor_id = Column(Integer, ForeignKey("constructors.id"), nullable=False)
    grid_position = Column(Integer)
    finish_position = Column(Integer)
    points = Column(Numeric(5, 2), nullable=False, default=0)
    status = Column(Text, nullable=False)
    fastest_lap = Column(Boolean, nullable=False, default=False)
    is_wet_race = Column(Boolean, nullable=False, default=False)

    race = relationship("Race", back_populates="results")
    driver = relationship("Driver")
    constructor = relationship("Constructor")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    trained_at = Column(DateTime(timezone=True), nullable=False)
    training_races_count = Column(Integer, nullable=False)
    notes = Column(Text)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    constructor_id = Column(Integer, ForeignKey("constructors.id"), nullable=False)
    predicted_position = Column(Integer, nullable=False)
    confidence_score = Column(Numeric(5, 4))
    created_at = Column(DateTime(timezone=True), nullable=False)

    race = relationship("Race", back_populates="predictions")
    driver = relationship("Driver")
    constructor = relationship("Constructor")


class EvaluationMetrics(Base):
    __tablename__ = "evaluation_metrics"

    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, ForeignKey("races.id"), nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    evaluated_at = Column(DateTime(timezone=True), nullable=False)
    top3_accuracy = Column(Numeric(5, 4))
    exact_position_accuracy = Column(Numeric(5, 4))
    mean_position_error = Column(Numeric(6, 4))

    race = relationship("Race", back_populates="evaluation_metrics")
