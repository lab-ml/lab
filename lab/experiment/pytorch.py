from typing import Optional

import tensorflow as tf

from lab import experiment
from lab.logger import tensorboard_writer


class Experiment(experiment.Experiment):
    """
    ## Experiment

    Each experiment has different configurations or algorithms.
    An experiment can have multiple trials.
    """

    def __init__(self, *,
                 name: str,
                 python_file: str,
                 comment: str,
                 check_repo_dirty: Optional[bool] = None,
                 is_log_python_file: Optional[bool] = None):
        """
        ### Create the experiment

        :param name: name of the experiment
        :param python_file: `__file__` that invokes this. This is stored in
         the experiments list.
        :param comment: a short description of the experiment
        :param check_repo_dirty: whether not to start the experiment if
         there are uncommitted changes.

        The experiments log keeps track of `python_file`, `name`, `comment` as
         well as the git commit.

        Experiment maintains the locations of checkpoints, logs, etc.
        """

        super().__init__(name=name,
                         python_file=python_file,
                         comment=comment,
                         check_repo_dirty=check_repo_dirty,
                         is_log_python_file=is_log_python_file)

    def load_checkpoint(self):
        raise NotImplementedError()

    def save_checkpoint(self):
        raise NotImplementedError()

    def create_writer(self):
        """
        ## Create TensorFlow summary writer
        """
        self.logger.add_writer(tensorboard_writer.Writer(
            tf.summary.FileWriter(str(self.info.summary_path))))

    def start_train(self, global_step: int):
        """
        ## Start experiment

        Load a checkpoint or reset based on `global_step`.
        """

        self.trial.start_step = global_step
        self._start()

        if global_step > 0:
            # load checkpoint if we are starting from middle
            with self.logger.section("Loading checkpoint") as m:
                m.is_successful = self.load_checkpoint()
        else:
            # initialize variables and clear summaries if we are starting from scratch
            with self.logger.section("Clearing summaries"):
                self.clear_summaries()
            with self.logger.section("Clearing checkpoints"):
                self.clear_checkpoints()

        self.create_writer()

    def start_replay(self):
        """
        ## Start replaying experiment

        Load a checkpoint or reset based on `global_step`.
        """

        with self.logger.section("Loading checkpoint") as m:
            m.is_successful = self.load_checkpoint()