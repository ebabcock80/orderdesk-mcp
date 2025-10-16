"""Test store management endpoints."""

import pytest
from fastapi import status


def test_create_store(client, auth_headers, test_store_data):
    """Test creating a store."""
    response = client.post("/stores", json=test_store_data, headers=auth_headers)
    assert response.status_code == status.HTTP_201_CREATED
    
    data = response.json()
    assert data["store_id"] == test_store_data["store_id"]
    assert data["label"] == test_store_data["label"]
    assert "id" in data
    assert "created_at" in data


def test_list_stores(client, auth_headers, test_store_data):
    """Test listing stores."""
    # Create a store first
    client.post("/stores", json=test_store_data, headers=auth_headers)
    
    # List stores
    response = client.get("/stores", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["store_id"] == test_store_data["store_id"]


def test_delete_store(client, auth_headers, test_store_data):
    """Test deleting a store."""
    # Create a store first
    create_response = client.post("/stores", json=test_store_data, headers=auth_headers)
    store_id = create_response.json()["id"]
    
    # Delete the store
    response = client.delete(f"/stores/{store_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify store is deleted
    list_response = client.get("/stores", headers=auth_headers)
    assert len(list_response.json()) == 0


def test_duplicate_store_creation(client, auth_headers, test_store_data):
    """Test creating duplicate stores."""
    # Create first store
    response1 = client.post("/stores", json=test_store_data, headers=auth_headers)
    assert response1.status_code == status.HTTP_201_CREATED
    
    # Try to create duplicate store
    response2 = client.post("/stores", json=test_store_data, headers=auth_headers)
    assert response2.status_code == status.HTTP_409_CONFLICT


def test_store_not_found(client, auth_headers):
    """Test accessing non-existent store."""
    response = client.delete("/stores/non-existent-id", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
