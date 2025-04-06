"""Automation orchestration using observer and pub/sub patterns.

N.B. This entire library must remain compatible with usage in CPython and MicroPython.
"""

import time
from collections import OrderedDict
from typing import Any
from typing import Callable
from typing import override

from huereka.shared.collections import Collection
from huereka.shared.collections import CollectionEntry
from huereka.shared.dependencies import Dependency
from huereka.shared.dependencies import Inputs
from huereka.shared.dependencies import States
from huereka.shared.micro_utils import property  # pylint: disable=redefined-builtin
from huereka.shared.micro_utils import uclass
from huereka.shared.properties import data_property

__pending_action_triggers__: dict[str, Any] = OrderedDict()
__prop_orchestrator__: Callable[[Any, str, Any, Any], None] | None = None


class AutomationDependency:  # pylint: disable=too-few-public-methods
    """Configuration for automating property change events."""

    def __init__(
        self,
        key: str,
    ) -> None:
        """Configure a property for automation.

        Args:
            key: Name of the property to associate with the data in automation events.
        """
        self.key = key


@uclass()
class Operation(CollectionEntry):
    """An expression, and the outputs to return, when certain conditions are met."""

    def __init__(
        self,
        *,
        uuid: str | None = None,
        name: str | None = None,
        expression: str | None = None,
        outputs: list[dict] | None = None,
        stop: bool = True,
    ) -> None:
        """Set up the initial operation values.

        Args:
            uuid: Ignored. Argument required for auto conversion.
            name: Ignored. Argument required for auto conversion.
            expression: Primary expression to evaluate to determine if outputs should be returned.
            outputs: Instructions to return when the expression evaluates to true.
            stop: Whether to stop future operations when the expression evaluates true.
        """
        # Operations are only attached inline to Actions in an ordered list, do not generate metadata.
        super().__init__(uuid="op", name="op")
        self._expression: str | None = None
        self._key: str | None = None
        self._op: str | None = None
        self._value: Any = None
        self._outputs: list | None = None
        self._stop = False
        self.expression = expression
        self.outputs = outputs or []
        self.stop = stop

    @property
    def expression(self) -> str:
        """The primary expression to evaluate to determine if results should be returned."""
        return self._expression

    @data_property(str, key="expr")
    @expression.setter
    def expression(self, expression: str) -> None:
        """Safely set the primary expression to evaluate to determine if results should be returned."""
        self._expression = expression
        # Cache the pieces of the operation to improve orchestration performance.
        self._key, self._op, self._value = expression.split()
        if self._value.startswith("'\""):
            self._value = self._value.strip("'\"")
        else:
            self._value = int(self._value)

    @override
    def to_json(self, save_only: bool = False) -> dict:
        result = super().to_json(save_only=save_only)
        # Discard ID and name, operations are only attached inline to Actions.
        result.pop("id")
        result.pop("name")
        return result

    @property
    def outputs(self) -> list[dict]:
        """Results to return when the expression evaluates to true."""
        return self._outputs

    @data_property(
        list,
        default=list,
        validator=lambda items: all(isinstance(item, dict) for item in items),
    )
    @outputs.setter
    def outputs(self, outputs: list[dict]) -> None:
        """Safely set the results to return when the expression evaluates to true."""
        self._outputs = outputs

    def run(self, args: dict[str, Any]) -> tuple[list[dict], bool]:
        """Execute the operation and return output instructions to process further.

        Args:
            args: Optional input arguments to use with the operation.

        Returns:
            Output instructions to process further.
        """
        value = args[self._key]
        matched = False
        if self._op == ">":
            matched = value > self._value
        elif self._op == ">=":
            matched = value >= self._value
        elif self._op == "<":
            matched = value < self._value
        elif self._op == "<=":
            matched = value <= self._value
        elif self._op in ("=", "=="):
            matched = value == self._value
        if matched:
            return self.outputs, self.stop
        return [], self.stop

    @property
    def stop(self) -> bool:
        """Whether to stop future operations when the expression evaluates true."""
        return self._stop

    @data_property(bool, default=True)
    @stop.setter
    def stop(self, stop: bool) -> None:
        """Safely set whether to stop future operations when the expression evaluates true."""
        self._stop = stop


@uclass()
class Action(CollectionEntry):
    """A collection of operations to perform."""

    def __init__(
        self,
        *,
        uuid: str | None = None,
        name: str | None = None,
        dependencies: list[Dependency] | None = None,
        operations: list[Operation] | None = None,
        expire: int | None = None,
    ) -> None:
        """Set up the initial action values.

        Args:
            uuid: Universally unique identifier.
            name: Human readable name used to store/reference in collections.
            dependencies: Dependencies used to trigger actions, and provide arguments to operations.
                Only uses "input" and "state" type dependencies.
                Any "input" types will cause the action to trigger, and be available to operations.
                Any "output" types will not cause the action to be triggered, but will be available to operations.
            operations: Collection of expressions, and their outputs to apply, when certain conditions are met.
            expire: Whether the action should automatically remove after triggering.
                e.g., 0/None = no expiration, 1 = expire on trigger, 2+ expire at given time.
        """
        super().__init__(uuid=uuid, name=name)
        self._dependencies: list[Dependency] | None = None
        self._inputs: list[str] = []
        self._states: list[str] = []
        self._operations: list[Operation] | None = None
        self._expire = 0
        self.dependencies = dependencies or []
        self.operations = operations or []
        self.expire = expire

    @property
    def dependencies(self) -> list[Dependency]:
        """Dependencies to use with operations."""
        return self._dependencies

    @data_property(
        list,
        key="deps",
        default=list,
        validator=lambda items: all(isinstance(item, (dict, Dependency)) for item in items),
        convert=Dependency,
    )
    @dependencies.setter
    def dependencies(self, dependencies: list[Dependency]) -> None:
        """Safely set the dependencies to use with operations."""
        self._dependencies = dependencies
        self._inputs.clear()
        self._states.clear()
        for dependency in dependencies:
            if isinstance(dependency, Inputs):
                self._inputs.append(str(dependency))
            if isinstance(dependency, States):
                self._states.append(str(dependency))

    @property
    def expire(self) -> int | None:
        """The expiration date for the action."""
        return self._expire

    @data_property(int, default=0)
    @expire.setter
    def expire(self, expire: int) -> None:
        """Safely set the expiration date for the action."""
        self._expire = expire

    @property
    def inputs(self) -> list[str]:
        """Inputs to use to trigger operations."""
        return self._inputs

    @property
    def operations(self) -> list[Operation]:
        """Operations to evaluate to create outputs."""
        return self._operations

    @data_property(
        list,
        key="ops",
        default=list,
        validator=lambda items: all(isinstance(item, (dict, Operation)) for item in items),
        convert=Operation,
    )
    @operations.setter
    def operations(self, operations: list[Operation]) -> None:
        """Safely set the operations to evaluate to create outputs."""
        self._operations = operations

    def run(self, args: dict[str, Any]) -> list[dict]:
        """Execute all operations and return output instructions to process further.

        Args:
            args: Optional input arguments to use with operations.

        Returns:
            Output instructions from all matching operations to process further.
        """
        outputs = []
        for operation in self._operations:
            results, stop = operation.run(args)
            outputs.extend(results)
            if stop:
                break
        return outputs

    @property
    def states(self) -> list[str]:
        """Stateful information to use with operations, but do not trigger."""
        return self._states


@uclass()
class Actions(Collection):
    """Singleton for managing all actions that trigger input/output operations."""

    collection_help: str = "actions"
    entry_cls: str = Action


def automate() -> Callable:
    """Wrap a property with additional metadata for triggering automation events."""

    def _wrapper(prop: property) -> property:
        """Update the property automation configuration."""
        prop_key = prop.fget.__name__
        prop.__automation_dependency__ = AutomationDependency(
            prop_key,
        )
        if prop.fset:
            original_fset = prop.fset

            def _setter(self: Any, value: Any) -> Any:
                """Call the property setter and trigger automation orchestration on changes."""
                if __prop_orchestrator__:
                    old_value = prop.fget(self)
                    original_fset(self, value)
                    new_value = prop.fget(self)
                    if old_value != new_value:
                        __prop_orchestrator__(  # pylint: disable=not-callable
                            self.uuid, prop.__automation_dependency__.key, old_value, new_value
                        )
                else:
                    original_fset(self, value)

            prop = prop.setter(_setter)
        return prop

    return _wrapper


def debug_print_orchestrator(uuid: str | dict, prop: str, old_value: Any, new_value: Any) -> None:
    """Print automation events for debugging purposes.

    Do not use in production.
    """
    print(uuid, prop, old_value, new_value)


def get_action_maps(actions: list[Action]) -> tuple[dict[str, list[Action]], dict[str, list[str]]]:
    """Generate mappings for actions based on their inputs/triggers.

    Args:
        actions: The actions to map to property triggers.

    Returns:
        A mapping of input triggers to applicable actions, and action IDs to input arguments.
    """
    action_trigger_map = {}
    action_arg_map = {}
    for action in actions:
        for trigger in action.inputs:
            action_trigger_map.setdefault(trigger, []).append(action)
            action_arg_map[action.uuid] = action.inputs + action.states
    return action_trigger_map, action_arg_map


def get_property_changes() -> dict[str, Any]:
    """Retrieve the built-in pending property change queue, and reset.

    Forces a clear of the built-in pending change queue to ensure all updates since the time
    of the original request are tracked separately.

    Returns:
        A copy of the property values that have changed since the previous request.
    """
    data = __pending_action_triggers__.copy()
    __pending_action_triggers__.clear()
    return data


def property_change_orchestrator(
    uuid: str | dict,
    prop: str,
    old_value: Any,  # pylint: disable=unused-argument
    new_value: Any,
) -> None:
    """Add a property change to the built-in pending property change queue.

    Can be called manually to queue a pending property change, such as lazily evaluated properties,
    or automatically when combined with `set_property_event_orchestrator()`.

    For use with `get_property_changes()` to act on the same built-in queue.

    Args:
        uuid: ID of the object where the property changed.
        prop: Name of the property that changed.
        old_value: Original value. Ignored. Required to match expected callback signature.
        new_value: Latest value set on a property.
    """
    __pending_action_triggers__[f"{prop}@{uuid}"] = new_value


def set_property_event_orchestrator(receiver: Callable) -> None:
    """Set the receiver to handle all property automation events.

    Args:
        receiver: Where to send property changes.
    """
    global __prop_orchestrator__  # pylint: disable=global-statement
    __prop_orchestrator__ = receiver


def process_property_changes(
    property_changes: dict[str, Any],
    action_trigger_map: dict[str, list[Action]],
    action_arg_map: dict[str, list[str]],
    get_props: Callable,
) -> tuple[dict[str, Any], list[str]]:
    """Create instructions to run based on changed properties tracked by actions.

    Args:
        property_changes: A mapping of all properties, and their values, representing changes in state.
            Used as baseline arguments to action operations.
        action_trigger_map: A mapping of input triggers to applicable actions.
        action_arg_map: Action IDs to input arguments.
        get_props: Function to call with a mapping of properties to request as additional input values for actions.
            Only requests the values for properties not in the original "property_changes".

    Returns:
        Mapping of property ID/values to apply, and actions that expired.
    """
    # Find all actions expected to trigger this cycle.
    pending_actions = []
    pending_args = {}
    for dep_key in property_changes.keys():
        if pending := action_trigger_map.get(dep_key):
            pending_actions.extend(pending)
            for action in pending:
                for key in action_arg_map[action.uuid]:
                    if key not in property_changes:
                        pending_args[key] = None
    if pending_args:
        property_changes |= get_props(pending_args)

    # Run and flatten all operations so that overlapping only apply once.
    results = {}
    expired = []
    for action in pending_actions:
        if outputs := action.run({key: property_changes[key] for key in action_arg_map[action.uuid]}):
            for output in outputs:
                results[output["prop"]] = output["value"]
            if action.expire == 1 or action.expire >= time.time():
                expired.append(action.uuid)

    return results, expired
