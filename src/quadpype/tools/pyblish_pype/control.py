"""The Controller in a Model/View/Controller-based application
The graphical components of Pyblish Lite use this object to perform
publishing. It communicates via the Qt Signals/Slots mechanism
and has no direct connection to any graphics. This is important,
because this is how unittests are able to run without requiring
an active window manager; such as via Travis-CI.
"""
import os
import sys
import inspect
import logging
import collections

from qtpy import QtCore

import pyblish.api
import pyblish.util
import pyblish.logic
import pyblish.lib
import pyblish.version

from . import util
from .constants import InstanceStates

from quadpype.settings import get_current_project_settings


class IterationBreak(Exception):
    pass


class MainThreadItem:
    """Callback with args and kwargs."""
    def __init__(self, callback, *args, **kwargs):
        self.callback = callback
        self.args = args
        self.kwargs = kwargs

    def process(self):
        self.callback(*self.args, **self.kwargs)


class MainThreadProcess(QtCore.QObject):
    """Qt based main thread process executor.

    Has timer which controls each 50ms if there is new item to process.

    This approach gives ability to update UI meanwhile plugin is in progress.
    """
    # How many times let pass QtApplication to process events
    # - use 2 as resize event can trigger repaint event but not process in
    #   same loop
    count_timeout = 2

    def __init__(self):
        super().__init__()
        self._items_to_process = collections.deque()

        timer = QtCore.QTimer()
        timer.setInterval(0)

        timer.timeout.connect(self._execute)

        self._timer = timer
        self._switch_counter = self.count_timeout

    def process(self, func, *args, **kwargs):
        item = MainThreadItem(func, *args, **kwargs)
        self.add_item(item)

    def add_item(self, item):
        self._items_to_process.append(item)

    def _execute(self):
        if not self._items_to_process:
            return

        if self._switch_counter > 0:
            self._switch_counter -= 1
            return

        self._switch_counter = self.count_timeout

        item = self._items_to_process.popleft()
        item.process()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()

    def clear(self):
        if self._timer.isActive():
            self._timer.stop()
        self._items_to_process = collections.deque()

    def stop_if_empty(self):
        if self._timer.isActive():
            item = MainThreadItem(self._stop_if_empty)
            self.add_item(item)

    def _stop_if_empty(self):
        if not self._items_to_process:
            self.stop()


class Controller(QtCore.QObject):
    log = logging.getLogger("PyblishController")
    # Emitted when the GUI is about to start processing;
    # e.g. resetting, validating or publishing.
    about_to_process = QtCore.Signal(object, object)

    # ??? Emitted for each process
    was_processed = QtCore.Signal(dict)

    # Emitted when reset
    # - all data are reset (plugins, processing, pari yielder, etc.)
    was_reset = QtCore.Signal()

    # Emitted when previous group changed
    passed_group = QtCore.Signal(object)

    # Emitted when want to change state of instances
    switch_toggleability = QtCore.Signal(bool)

    # On action finished
    was_acted = QtCore.Signal(dict)

    # Emitted when processing has stopped
    was_stopped = QtCore.Signal()

    # Emitted when processing has finished
    was_finished = QtCore.Signal()

    # Emitted when plugin was skipped
    was_skipped = QtCore.Signal(object)

    # store OrderGroups - now it is a singleton
    order_groups = util.OrderGroups

    # When instance is toggled
    instance_toggled = QtCore.Signal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.context = None
        self.plugins = {}
        self.optional_default = {}
        self.instance_toggled.connect(self._on_instance_toggled)
        self._main_thread_processor = MainThreadProcess()

        self._current_state = ""

    def reset_variables(self):
        self.log.debug("Resetting pyblish context variables")

        # Data internal to the GUI itself
        self.is_running = False
        self.stopped = False
        self.errored = False
        self._current_state = ""

        # Active producer of pairs
        self.pair_generator = None
        # Active pair
        self.current_pair = None

        # Orders which changes GUI
        # - passing collectors order disables plugin/instance toggle
        self.collect_state = 0

        # - passing validators order disables validate button and gives ability
        #   to know when to stop on validate button press
        self.validators_order = None
        self.validated = False

        # Get collectors and validators order
        plugin_groups_keys = list(self.order_groups.groups.keys())
        self.validators_order = self.order_groups.validation_order
        next_group_order = None
        if len(plugin_groups_keys) > 1:
            next_group_order = plugin_groups_keys[1]

        # This is used to track whether or not to continue
        # processing when, for example, validation has failed.
        self.processing = {
            "stop_on_validation": False,
            # Used?
            "last_plugin_order": None,
            "current_group_order": plugin_groups_keys[0],
            "next_group_order": next_group_order,
            "nextOrder": None,
            "ordersWithError": set()
        }
        self._set_state_by_order()
        self.log.debug("Reset of pyblish context variables done")

    @property
    def current_state(self):
        return self._current_state

    def presets_by_hosts(self):
        # Get global filters as base
        presets = get_current_project_settings()
        if not presets:
            return {}

        result = presets.get("global", {}).get("filters", {})
        hosts = pyblish.api.registered_hosts()
        for host in hosts:
            host_presets = presets.get(host, {}).get("filters")
            if not host_presets:
                continue

            for key, value in host_presets.items():
                if value is None:
                    if key in result:
                        result.pop(key)
                    continue

                result[key] = value

        return result

    def reset_context(self):
        self.log.debug("Resetting pyblish context object")

        comment = None
        if (
            self.context is not None and
            self.context.data.get("comment") and
            # We only preserve the user typed comment if we are *not*
            # resetting from a successful publish without errors
            self._current_state != "Published"
        ):
            comment = self.context.data["comment"]

        self.context = pyblish.api.Context()

        self.context._publish_states = InstanceStates.ContextType
        self.context.optional = False

        self.context.data["publish"] = True
        self.context.data["name"] = "context"

        self.context.data["host"] = reversed(pyblish.api.registered_hosts())
        self.context.data["port"] = int(
            os.getenv("PYBLISH_CLIENT_PORT", -1)
        )
        self.context.data["connectTime"] = pyblish.lib.time(),
        self.context.data["pyblishVersion"] = pyblish.version,
        self.context.data["pythonVersion"] = sys.version

        self.context.data["icon"] = "book"

        self.context.families = ("__context__",)

        if comment:
            # Preserve comment on reset if user previously had a comment
            self.context.data["comment"] = comment

        self.log.debug("Reset of pyblish context object done")

    def reset(self):
        """Discover plug-ins and run collection."""
        self._main_thread_processor.clear()
        self._main_thread_processor.process(self._reset)
        self._main_thread_processor.start()

    def _reset(self):
        self.reset_context()
        self.reset_variables()

        self.possible_presets = self.presets_by_hosts()

        # Load plugins and set pair generator
        self.load_plugins()
        self.pair_generator = self._pair_yielder(self.plugins)

        self.was_reset.emit()

        # Process collectors load rest of plugins with collected instances
        self.collect()

    def load_plugins(self):
        self.test = pyblish.logic.registered_test()
        self.optional_default = {}

        plugins = pyblish.api.discover()

        targets = set(pyblish.logic.registered_targets())
        targets.add("default")
        targets = list(targets)
        plugins_by_targets = pyblish.logic.plugins_by_targets(plugins, targets)

        _plugins = []
        for plugin in plugins_by_targets:
            # Skip plugin if is not optional and not active
            if (
                not getattr(plugin, "optional", False)
                and not getattr(plugin, "active", True)
            ):
                continue
            _plugins.append(plugin)
        self.plugins = _plugins

    def on_published(self):
        if self.is_running:
            self.is_running = False
        self._current_state = (
            "Published" if not self.errored else "Published, with errors"
        )
        self.was_finished.emit()
        self._main_thread_processor.stop()

    def stop(self):
        self.log.debug("Stopping")
        self.stopped = True

    def act(self, plugin, action):
        self.is_running = True
        item = MainThreadItem(self._process_action, plugin, action)
        self._main_thread_processor.add_item(item)
        self._main_thread_processor.start()
        self._main_thread_processor.stop_if_empty()

    def _process_action(self, plugin, action):
        result = pyblish.plugin.process(
            plugin, self.context, None, action.id
        )
        self.is_running = False
        self.was_acted.emit(result)

    def emit_(self, signal, kwargs):
        pyblish.api.emit(signal, **kwargs)

    def _process(self, plugin, instance=None):
        """Produce `result` from `plugin` and `instance`
        :func:`process` shares state with :func:`_iterator` such that
        an instance/plugin pair can be fetched and processed in isolation.
        Arguments:
            plugin (pyblish.api.Plugin): Produce result using plug-in
            instance (optional, pyblish.api.Instance): Process this instance,
                if no instance is provided, context is processed.
        """

        self.processing["nextOrder"] = plugin.order

        try:
            result = pyblish.plugin.process(plugin, self.context, instance)
            # Make note of the order at which the
            # potential error error occurred.
            if result["error"] is not None:
                self.processing["ordersWithError"].add(plugin.order)

        except Exception as exc:
            raise Exception("Unknown error({}): {}".format(
                plugin.__name__, str(exc)
            ))

        return result

    def _pair_yielder(self, plugins):
        for plugin in plugins:
            if (
                self.processing["current_group_order"] is not None
                and plugin.order > self.processing["current_group_order"]
            ):
                current_group_order = self.processing["current_group_order"]

                new_next_group_order = None
                new_current_group_order = self.processing["next_group_order"]
                if new_current_group_order is not None:
                    current_next_order_found = False
                    for order in self.order_groups.groups.keys():
                        if current_next_order_found:
                            new_next_group_order = order
                            break

                        if order == new_current_group_order:
                            current_next_order_found = True

                self.processing["next_group_order"] = new_next_group_order
                self.processing["current_group_order"] = (
                    new_current_group_order
                )

                # Force update to the current state
                self._set_state_by_order()

                if self.collect_state == 0:
                    self.collect_state = 1
                    self._current_state = (
                        "Ready" if not self.errored else
                        "Collected, with errors"
                    )
                    self.switch_toggleability.emit(True)
                    self.passed_group.emit(current_group_order)
                    yield IterationBreak("Collected")

                else:
                    self.passed_group.emit(current_group_order)
                    if self.errored:
                        self._current_state = (
                            "Stopped, due to errors" if not
                            self.processing["stop_on_validation"] else
                            "Validated, with errors"
                        )
                        yield IterationBreak("Last group errored")

            if self.collect_state == 1:
                self.collect_state = 2
                self.switch_toggleability.emit(False)

            if not self.validated and plugin.order > self.validators_order:
                self.validated = True
                if self.processing["stop_on_validation"]:
                    self._current_state = (
                        "Validated" if not self.errored else
                        "Validated, with errors"
                    )
                    yield IterationBreak("Validated")

            # Stop if was stopped
            if self.stopped:
                self.stopped = False
                self._current_state = "Paused"
                yield IterationBreak("Stopped")

            # check test if will stop
            self.processing["nextOrder"] = plugin.order
            message = self.test(**self.processing)
            if message:
                self._current_state = "Paused"
                yield IterationBreak("Stopped due to \"{}\"".format(message))

            self.processing["last_plugin_order"] = plugin.order
            if not plugin.active:
                pyblish.logic.log.debug("%s was inactive, skipping.." % plugin)
                self.was_skipped.emit(plugin)
                continue

            in_collect_stage = self.collect_state == 0
            if plugin.__instanceEnabled__:
                instances = pyblish.logic.instances_by_plugin(
                    self.context, plugin
                )
                if not instances:
                    self.was_skipped.emit(plugin)
                    continue

                for instance in instances:
                    if (
                        not in_collect_stage
                        and instance.data.get("publish") is False
                    ):
                        pyblish.logic.log.debug(
                            "%s was inactive, skipping.." % instance
                        )
                        continue
                    # Stop if was stopped
                    if self.stopped:
                        self.stopped = False
                        self._current_state = "Paused"
                        yield IterationBreak("Stopped")

                    yield (plugin, instance)
            else:
                families = util.collect_families_from_instances(
                    self.context, only_active=not in_collect_stage
                )
                plugins = pyblish.logic.plugins_by_families(
                    [plugin], families
                )
                if not plugins:
                    self.was_skipped.emit(plugin)
                    continue
                yield (plugin, None)

        self.passed_group.emit(self.processing["next_group_order"])

    def iterate_and_process(self, on_finished=None):
        """ Iterating inserted plugins with current context.
        Collectors do not contain instances, they are None when collecting!
        This process don't stop on one
        """
        self._main_thread_processor.start()

        def on_next():
            self.log.debug("Looking for next pair to process")
            try:
                self.current_pair = next(self.pair_generator)
                if isinstance(self.current_pair, IterationBreak):
                    raise self.current_pair

            except IterationBreak:
                self.log.debug("Iteration break was raised")
                self.is_running = False
                self.was_stopped.emit()
                self._main_thread_processor.stop()
                return

            except StopIteration:
                self.log.debug("Iteration stop was raised")
                self.is_running = False
                # All pairs were processed successfully!
                if on_finished is not None:
                    self._main_thread_processor.add_item(
                        MainThreadItem(on_finished)
                    )
                self._main_thread_processor.stop_if_empty()
                return

            except Exception as exc:
                self.log.warning(
                    "Unexpected exception during `on_next` happened",
                    exc_info=True
                )
                exc_msg = str(exc)
                self._main_thread_processor.add_item(
                    MainThreadItem(on_unexpected_error, error=exc_msg)
                )
                return

            self.about_to_process.emit(*self.current_pair)
            self._main_thread_processor.add_item(
                MainThreadItem(on_process)
            )

        def on_process():
            try:
                self.log.debug(
                    "Processing pair: {}".format(str(self.current_pair))
                )
                result = self._process(*self.current_pair)
                if result["error"] is not None:
                    self.log.debug("Error happened")
                    self.errored = True

                self.log.debug("Pair processed")
                self.was_processed.emit(result)

            except Exception as exc:
                self.log.warning(
                    "Unexpected exception during `on_process` happened",
                    exc_info=True
                )
                exc_msg = str(exc)
                self._main_thread_processor.add_item(
                    MainThreadItem(on_unexpected_error, error=exc_msg)
                )
                return

            self._main_thread_processor.add_item(
                MainThreadItem(on_next)
            )

        def on_unexpected_error(error):
            # TODO this should be handled much differently
            # TODO emit crash signal to show message box with traceback?
            self.is_running = False
            self.was_stopped.emit()
            util.u_print(u"An unexpected error occurred:\n %s" % error)
            if on_finished is not None:
                self._main_thread_processor.add_item(
                    MainThreadItem(on_finished)
                )
            self._main_thread_processor.stop_if_empty()

        self.is_running = True
        self._main_thread_processor.add_item(
            MainThreadItem(on_next)
        )

    def _set_state_by_order(self):
        order = self.processing["current_group_order"]
        self._current_state = self.order_groups.groups[order]["state"]

    def collect(self):
        """ Iterate and process Collect plugins
        - load_plugins method is launched again when finished
        """
        self._set_state_by_order()
        self._main_thread_processor.process(self._start_collect)
        self._main_thread_processor.start()

    def validate(self):
        """ Process plugins to validations_order value."""
        self._set_state_by_order()
        self._main_thread_processor.process(self._start_validate)
        self._main_thread_processor.start()

    def publish(self):
        """ Iterate and process all remaining plugins."""
        self._set_state_by_order()
        self._main_thread_processor.process(self._start_publish)
        self._main_thread_processor.start()

    def _start_collect(self):
        self.iterate_and_process()

    def _start_validate(self):
        self.processing["stop_on_validation"] = True
        self.iterate_and_process()

    def _start_publish(self):
        self.processing["stop_on_validation"] = False
        self.iterate_and_process(self.on_published)

    def cleanup(self):
        """Forcefully delete objects from memory
        In an ideal world, this shouldn't be necessary. Garbage
        collection guarantees that anything without reference
        is automatically removed.
        However, because this application is designed to be run
        multiple times from the same interpreter process, extra
        case must be taken to ensure there are no memory leaks.
        Explicitly deleting objects shines a light on where objects
        may still be referenced in the form of an error. No errors
        means this was unnecessary, but that's ok.
        """

        for instance in self.context:
            del(instance)

        for plugin in self.plugins:
            del(plugin)

    def _on_instance_toggled(self, instance, old_value, new_value):
        callbacks = pyblish.api.registered_callbacks().get("instanceToggled")
        if not callbacks:
            return

        for callback in callbacks:
            try:
                callback(instance, old_value, new_value)
            except Exception:
                self.log.warning(
                    "Callback for `instanceToggled` crashed. {}".format(
                        os.path.abspath(inspect.getfile(callback))
                    ),
                    exc_info=True
                )
