import logging
from typing import Callable, Sequence
from contextlib import contextmanager
from datetime import datetime
import time

from tqdm.rich import tqdm
import ray

from deric.utils.logging import console


def parallel(
    on: Sequence,
    do: ray.remote_function.RemoteFunction,
    then: Callable,
    _disable_tqdm: bool = False,
    _max_tasks: int = 32,
    **kwargs,
):
    """
    Run "do" for each "on" and "then" on its result(s).
    """
    result_refs = []
    iter_on = tqdm(range(len(on)), smoothing=0) if not _disable_tqdm else range(len(on))

    def ready_get(refs):
        ready = ray.get(refs)
        for single in ready:
            try:
                then(single)
            except Exception as e:  # ignore fails on single items
                logging.exception(e)
                if __debug__:
                    raise e

    for i in iter_on:
        if len(result_refs) > _max_tasks:
            # update result_refs to only
            # track the remaining tasks.
            ready_refs, result_refs = ray.wait(result_refs, num_returns=1)
            ready_get(ready_refs)

        result_refs.append(do.remote(on[i], **kwargs))

        # get any possible remaining task on last iteration
        # the reason for doing it here is to prevent outputting things
        #   after we exit the progress bar context.
        if i == len(on) - 1:
            ready_get(result_refs)


def chunk(xs: list, chunk_size) -> list[list]:
    """
    Splits an iterable evenly in chunks
    """
    return [xs[i : i + chunk_size] for i in range(0, len(xs) or 1, max(1, chunk_size))]


@contextmanager
def rayruntime(config):
    """
    Context manager to provide automatic ray initialization and shutdown
    """
    # Initialize ray with provided config and run initialization tasks
    start_time = time.time()
    logging.info(f"Main started on: {datetime.now()}")
    if config.ray_address:
        ray.init(
            address=config.ray_address,
            local_mode=config.debug,
            log_to_driver=config.debug,
        )
    else:
        ray.init(
            num_cpus=config.max_tasks,
            local_mode=config.debug,
            log_to_driver=config.debug,
        )

    logging.info("Running %s", config.subcommand)
    console.line()
    try:
        yield
    finally:
        # Shutdown ray and perform exit tasks
        ray.shutdown()
        logging.info("Main finished after --- %s seconds ---", time.time() - start_time)
