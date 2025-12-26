import json
from pathlib import Path

import pytest

import main


@pytest.fixture(scope="session", autouse=True)
def load_sample_data():
    train_list_path = Path("train_data/train_list20250223.json")
    no_list_path = Path("train_data/no_list20250223.json")
    main.train_list = json.loads(train_list_path.read_text())
    main.no_list = json.loads(no_list_path.read_text())
