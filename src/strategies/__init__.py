"""Strategy plugin contracts, manifest models, and execution registry.

The registry and base types are NOT eagerly imported because they
transitively pull in pydantic, execution barrel, and broker chains.
Consumers should import from the specific module:

    from src.strategies.base import StrategyContext, StrategyPluginProtocol
    from src.strategies.registry import StrategyEngine, StrategyManifest
    from src.strategies.round_number_rejection import RoundNumberRejectionStrategy
"""

__all__: list[str] = []
