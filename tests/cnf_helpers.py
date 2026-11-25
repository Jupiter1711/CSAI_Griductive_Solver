from itertools import product


def is_cnf_satisfiable_with_primary_assignment(
    cnf, primary_assignment, auxiliary_count
):
    """
    primary_assignment:
        dict[int, bool], key là ID biến chính.
    """

    primary_count = len(primary_assignment)

    for auxiliary_values in product(
        (False, True),
        repeat=auxiliary_count,
    ):
        assignment = dict(primary_assignment)

        for i, value in enumerate(auxiliary_values):
            assignment[primary_count + i + 1] = value

        satisfied = True

        for clause in cnf:
            clause_satisfied = any(
                (literal > 0 and assignment[abs(literal)])
                or (literal < 0 and not assignment[abs(literal)])
                for literal in clause
            )

            if not clause_satisfied:
                satisfied = False
                break

        if satisfied:
            return True

    return False
