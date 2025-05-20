from typing import List, Dict

# Mock candidate database
CANDIDATES: List[Dict] = [
    {"id": "1", "name": "Alice", "experience": 5, "location": "Mumbai", "department": "Engineering"},
    {"id": "2", "name": "Bob", "experience": 3, "location": "Delhi", "department": "HR"},
    {"id": "3", "name": "Charlie", "experience": 7, "location": "Bengaluru", "department": "Engineering"},
]

def search_candidates(experience: int, location: str, department: str) -> List[Dict]:
    return [
        c for c in CANDIDATES
        if c["experience"] >= experience
        and c["location"].lower() == location.lower()
        and c["department"].lower() == department.lower()
    ]