# AUTOGENERATED! DO NOT EDIT! File to edit: ../notebooks/00_filters.ipynb.

# %% auto 0
__all__ = ['gaussian_filter', 'hessian', 'hessian_eigenvalues', 'frangi']

# %% ../notebooks/00_filters.ipynb 3
from math import ceil, sqrt
from typing import Callable

import torch
import torch.nn.functional as F

# %% ../notebooks/00_filters.ipynb 5
def gaussian_filter(
    img: torch.Tensor,  # The input tensor
    sigma: float,  # Standard deviation for the Gaussian kernel
    order: int | list = 0,  # The order of the filter's derivative along each dim
    mode: str = "reflect",  # Padding mode for `torch.nn.functional.pad`
    truncate: float = 4.0,  # Number of standard deviations to sample the filter
) -> torch.Tensor:
    """
    Convolves an image with a Gaussian kernel (or its derivatives).

    Inspired by the API of `scipy.ndimage.gaussian_filter` and the
    implementation of `diplib.Gauss`.
    """

    # Specify the dimensions of the convolution to use
    ndim = img.ndim - 2
    if isinstance(order, int):
        order = [order] * ndim
    else:
        assert len(order) == ndim, "Specify the Gaussian derivative order for each dim"
    convfn = getattr(F, f"conv{ndim}d")

    # Convolve along the rows, columns, and depth (optional)
    for dim, derivative_order in enumerate(order):
        img = _conv(img, convfn, sigma, derivative_order, truncate, mode, dim)
    return img

# %% ../notebooks/00_filters.ipynb 6
def _gaussian_kernel_1d(
    sigma: float, order: int, truncate: float, dtype: torch.dtype, device: torch.device
) -> torch.Tensor:
    # Set the size of the kernel according to the sigma
    radius = ceil(sigma * truncate)
    x = torch.arange(-radius, radius + 1, dtype=dtype, device=device)

    # Initialize the zeroth-order Gaussian kernel
    var = sigma**2
    g = (-x.pow(2) / (2 * var)).exp() / (sqrt(2 * torch.pi) * sigma)

    # Optionally convert to a higher-order kernel
    if order == 0:
        return g
    elif order == 1:
        g1 = g * (-x / var)
        g1 -= g1.mean()
        g1 /= (g1 * x).sum() / -1  # Normalize the filter's impulse response to -1
        return g1
    elif order == 2:
        g2 = g * (x.pow(2) / var - 1) / var
        g2 -= g2.mean()
        g2 /= (g2 * x.pow(2)).sum() / 2  # Normalize the filter's impulse response to 2
        return g2
    else:
        raise NotImplementedError(f"Only supports order in [0, 1, 2], not {order}")


def _conv(
    img: torch.Tensor,
    convfn: Callable,
    sigma: float,
    order: int,
    truncate: float,
    mode: str,
    dim: int,
):
    # Make a 1D kernel and pad such that the image size remains the same
    kernel = _gaussian_kernel_1d(sigma, order, truncate, img.dtype, img.device)
    padding = len(kernel) // 2

    # Specify the padding dimensions
    pad = [0] * 2 * (img.ndim - 2)
    for idx in range(2 * dim, 2 * dim + 2):
        pad[idx] = padding
    pad = pad[::-1]
    x = F.pad(img, pad, mode=mode)

    # Specify the dimension along which to do the convolution
    view = [1] * img.ndim
    view[dim + 2] *= -1

    return convfn(x, weight=kernel.view(*view))

# %% ../notebooks/00_filters.ipynb 8
from .linalg import eigvalsh2, eigvalsh3


def hessian(
    img: torch.Tensor, sigma: float, as_matrix: bool = False, **kwargs
) -> torch.Tensor:
    """Compute the Hessian of a 2D or 3D image."""
    if img.ndim == 4:
        hessian = _hessian_2d(img, sigma, **kwargs)
    elif img.ndim == 5:
        hessian = _hessian_3d(img, sigma, **kwargs)
    else:
        raise ValueError(f"img can only be 2D or 3D, not {img.ndim-2}D")

    if as_matrix:
        return _hessian_as_matrix(*hessian)
    else:
        return hessian


def hessian_eigenvalues(img: torch.Tensor, sigma: float, **kwargs):
    H = hessian(img, sigma, **kwargs)
    if len(H) == 3:
        eig = eigvalsh2(*H)
    elif len(H) == 6:
        eig = eigvalsh3(*H)
    else:
        raise ValueError(f"Unrecognized number of upper triangular elements: {len(H)}")

    # Sort the eigenvalues such that |lambda[1]| <= ... <= |lambda[n]|
    return torch.take_along_dim(eig, eig.abs().argsort(dim=1), dim=1)

# %% ../notebooks/00_filters.ipynb 9
def _hessian_2d(img: torch.Tensor, sigma: float, **kwargs):
    xx = gaussian_filter(img, sigma, order=[0, 2], **kwargs)
    yy = gaussian_filter(img, sigma, order=[2, 0], **kwargs)
    xy = gaussian_filter(img, sigma, order=[1, 1], **kwargs)
    return xx, xy, yy


def _hessian_3d(
    img: torch.Tensor, sigma: float, truncate: float = 4.0, mode: str = "reflect"
):
    # Precompute 1D kernels for the zeroth, first, and second derivatives
    g0 = _gaussian_kernel_1d(sigma, 0, truncate, img.dtype, img.device)
    g1 = _gaussian_kernel_1d(sigma, 1, truncate, img.dtype, img.device)
    g2 = _gaussian_kernel_1d(sigma, 2, truncate, img.dtype, img.device)
    padding = len(g0) // 2

    # Fuse individual kernels into a multi-channel 1D kernel
    kx = torch.concat(
        [
            g2.view(1, 1, 1, 1, -1),
            g1.view(1, 1, 1, 1, -1),
            g1.view(1, 1, 1, 1, -1),
            g0.view(1, 1, 1, 1, -1),
            g0.view(1, 1, 1, 1, -1),
            g0.view(1, 1, 1, 1, -1),
        ],
        dim=0,
    )
    ky = torch.concat(
        [
            g0.view(1, 1, 1, -1, 1),
            g1.view(1, 1, 1, -1, 1),
            g0.view(1, 1, 1, -1, 1),
            g2.view(1, 1, 1, -1, 1),
            g1.view(1, 1, 1, -1, 1),
            g0.view(1, 1, 1, -1, 1),
        ],
        dim=0,
    )
    kz = torch.concat(
        [
            g0.view(1, 1, -1, 1, 1),
            g0.view(1, 1, -1, 1, 1),
            g1.view(1, 1, -1, 1, 1),
            g0.view(1, 1, -1, 1, 1),
            g1.view(1, 1, -1, 1, 1),
            g2.view(1, 1, -1, 1, 1),
        ],
        dim=0,
    )

    # Run vectorized convolutions over each dimension
    x = img.expand(-1, 6, -1, -1, -1)
    x = F.conv3d(x, weight=kx, padding=(padding, 0, 0), groups=6)
    x = F.conv3d(x, weight=ky, padding=(0, padding, 0), groups=6)
    x = F.conv3d(x, weight=kz, padding=(0, 0, padding), groups=6)

    return x.split(1, 1)


def _hessian_as_matrix(*args):
    if len(args) == 3:
        xx, xy, yy = args
        return torch.stack(
            [
                torch.concat([xx, xy], dim=1),
                torch.concat([xy, yy], dim=1),
            ],
            dim=1,
        )
    elif len(args) == 6:
        xx, xy, xz, yy, yz, zz = args
        return torch.stack(
            [
                torch.concat([xx, xy, xz], dim=1),
                torch.concat([xy, yy, yz], dim=1),
                torch.concat([xz, yz, zz], dim=1),
            ],
            dim=1,
        )
    else:
        raise ValueError(f"Invalid number of arguments: {len(args)}")

# %% ../notebooks/00_filters.ipynb 11
def frangi(
    image: torch.Tensor,  # The intput image
    sigma_range: tuple = (1, 10),  # The range of sigmas to use
    scale_step: int = 2,  # The step between sigmas
    sigmas: list = None,  # Optional list of sigmas to use
    alpha: float = 0.5,  # Plate-like and line-like structures threshold
    beta: float = 0.5,  # Blob-like structures threshold
    gamma: float = None,  # Second-order structure threshold
    eps: float = 1e-10,
    device: str | torch.device = None,
) -> torch.tensor:

    # torch.backends.cudnn.enabled = False # more memory intensive but faster
    if image.ndim not in (4, 5):
        raise ValueError(
            f"input image must be 2D or 3D with shape [B C H W] or [B C D H W], received shape: {image.shape}",
        )

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # converting the input to float32 and moving it to the device
    alpha = torch.tensor(alpha, dtype=torch.float32, device=device)
    beta = torch.tensor(beta, dtype=torch.float32, device=device)
    eps = torch.tensor(eps, dtype=torch.float32, device=device)
    image = image.to(device=device, dtype=torch.float32)

    # if sigmas is not provided, generate them
    if isinstance(sigmas, list):
        sigmas = torch.tensor(sigmas, dtype=torch.float32, device=device)
    else:
        sigmas = torch.arange(
            sigma_range[0],
            sigma_range[1],
            scale_step,
            dtype=torch.float32,
            device=device,
        )
    if torch.any(sigmas < 0.0):
        raise ValueError("Sigma values must be positive")

    filtered_max = torch.zeros_like(image, dtype=torch.float32, device=device)

    for sigma in sigmas:
        eigenvalues = hessian_eigenvalues(image, sigma).squeeze()
        eigenvalues = torch.take_along_dim(eigenvalues, abs(eigenvalues).argsort(0), 0)
        lambda1 = eigenvalues[0]

        if image.ndim == 4:
            (lambda2,) = torch.maximum(eigenvalues[1:], eps)
            lambda2 = lambda2
            r_a = torch.inf
            r_b = torch.abs(lambda1 / lambda2)  # eq 15
            r_b = torch.nan_to_num(r_b, nan=0.0)

        elif image.ndim == 5:
            lambda2, lambda3 = torch.maximum(eigenvalues[1:], eps)
            r_a = lambda2 / lambda3  # eq 11
            r_b = abs(lambda1) / torch.sqrt(lambda2 * lambda3)  # eq 10

        eigenvalues = torch.sqrt((eigenvalues**2).sum(dim=0))  # eq 12
        if gamma is None:
            gamma_t = eigenvalues.max() / 2
            if gamma_t == 0:
                gamma_t = 1
        else:
            gamma_t = gamma
        result = 1.0 - torch.exp(-(r_a**2) / (2 * alpha**2))
        result = result * (torch.exp(-(r_b**2) / (2 * beta**2 + eps)))
        result = result * (1.0 - torch.exp(-(eigenvalues**2) / (2 * gamma_t**2 + eps)))

        filtered_max = torch.maximum(filtered_max, result)

    return filtered_max
