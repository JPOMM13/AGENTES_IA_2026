import os
from contextlib import contextmanager

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def get_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


@contextmanager
def neo4j_session():
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    driver = get_driver()
    try:
        with driver.session(database=database) as session:
            yield session
    finally:
        driver.close()


def run_read(cypher, **params):
    with neo4j_session() as session:
        result = session.run(cypher, **params)
        return [record.data() for record in result]
