"""Numerical linear algebra utilities"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/01_linalg.ipynb.

# %% auto 0
__all__ = ['eigvalsh', 'eigvalsh2', 'eigvalsh3']

# %% ../notebooks/01_linalg.ipynb 3
import torch

# %% ../notebooks/01_linalg.ipynb 5
def _is_square(A: torch.Tensor) -> bool:
    _, i, j, *_ = A.shape
    assert i == j, "Matrix is not square"


def _is_hermitian(A: torch.Tensor) -> bool:
    return torch.testing.assert_close(
        A, A.transpose(1, 2).conj(), msg="Matrix is not Hermitian"
    )

# %% ../notebooks/01_linalg.ipynb 6
def eigvalsh(A: torch.Tensor, check_valid: bool = True) -> torch.Tensor:
    """
    Compute the eigenvalues of a batched tensor with shape [B C C H W (D)]
    where C is 2 or 3, and the tensor is Hermitian in dimensions 1 and 2.

    Returns eigenvalues in a tensor with shape [1 2 H W] or [1 3 H W D],
    for 2D and 3D inputs, respectively, sorted in ascending order.
    """
    if check_valid:
        _is_square(A)
        _is_hermitian(A)
    if A.shape[1] == 2:
        return eigvalsh2(*A[:, *torch.triu_indices(2, 2)].split(1, dim=1))
    elif A.shape[1] == 3:
        return eigvalsh3(*A[:, *torch.triu_indices(3, 3)].split(1, dim=1))
    else:
        raise ValueError("Only supports 2×2 and 3×3 matrices")

# %% ../notebooks/01_linalg.ipynb 7
def eigvalsh2(ii: torch.Tensor, ij: torch.Tensor, jj: torch.Tensor) -> torch.Tensor:
    """
    Compute the eigenvalues of a batched Hermitian 2×2 tensor
    where blocks have shape [1 1 H W].

    Returns eigenvalues in a tensor with shape [1 2 H W]
    sorted in ascending order.
    """
    tr = ii + jj
    det = ii * jj - ij.square()

    disc = (tr.square() - 4 * det).clamp(0).sqrt()
    disc = torch.concat([-disc, disc], dim=1)

    eigvals = (tr + disc) / 2
    return eigvals

# %% ../notebooks/01_linalg.ipynb 8
def eigvalsh3(
    ii: torch.Tensor,
    ij: torch.Tensor,
    ik: torch.Tensor,
    jj: torch.Tensor,
    jk: torch.Tensor,
    kk: torch.Tensor,
    eps: float = 1e-8,
) -> torch.Tensor:
    """
    Compute the eigenvalues of a batched Hermitian 3×3 tensor
    where blocks have shape [1 1 H W D].

    Returns eigenvalues in a tensor with shape [1 3 H W D]
    sorted in ascending order.
    """
    diag = torch.concat([ii, jj, kk], dim=1)
    triu = torch.concat([ij, ik, jk], dim=1)

    q = diag.sum(dim=1, keepdim=True) / 3
    p1 = triu.square().sum(dim=1, keepdim=True)
    p2 = (diag - q).square().sum(dim=1, keepdim=True)
    p = ((2 * p1 + p2) / 6).sqrt()

    r = deth3(ii - q, ij, ik, jj - q, jk, kk - q) / (p.pow(3) + eps) / 2
    r = r.clamp(-1, 1)
    phi = r.arccos() / 3

    eig3 = q + 2 * p * phi.cos()
    eig1 = q + 2 * p * (phi + 2 * torch.pi / 3).cos()
    eig2 = 3 * q - eig1 - eig3
    return torch.concat([eig1, eig2, eig3], dim=1)

# %% ../notebooks/01_linalg.ipynb 9
def deth3(ii, ij, ik, jj, jk, kk):
    return (
        ii * jj * kk
        + 2 * ij * ik * jk
        - ii * jk.square()
        - jj * ik.square()
        - kk * ij.square()
    )
