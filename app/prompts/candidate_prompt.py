def generate_candidate_prompt(experience: int, location: str, department: str) -> str:
    return (
        f"Find candidates with at least {experience} years of experience, "
        f"located in {location}, "
        f"in the {department} department. "
        "Return comprehensive candidate profiles."
    )