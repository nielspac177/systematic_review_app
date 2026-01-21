"""Data extraction module for systematic review application."""

from .field_recommender import FieldRecommender, DEFAULT_FIELDS
from .data_extractor import DataExtractor

__all__ = [
    "FieldRecommender",
    "DataExtractor",
    "DEFAULT_FIELDS",
]
