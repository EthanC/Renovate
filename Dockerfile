FROM python:3.12.3-slim-bullseye

WORKDIR /renovate

# Install and configure Poetry
# https://github.com/python-poetry/poetry
RUN pip install poetry
RUN poetry config virtualenvs.create false

# Install dependencies
COPY pyproject.toml pyproject.toml
RUN poetry install --no-root

COPY . .

CMD [ "python", "renovate.py" ]
