from __future__ import annotations

from enum import Enum


class Action:
    class Kind(Enum):
        CHECK = "check"
        CALL = "call"
        RAISE = "raise"
        FOLD = "fold"

    def __init__(self, kind: Action.Kind, amount: int | None = None):
        if not isinstance(kind, Action.Kind):
            type_name = type(kind).__name__
            article = "an" if type_name.startswith(('a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U')) else "a"
            raise TypeError(f"Expected 'kind' to be an Action.Kind, but it was {article} {type_name}")

        self.kind = kind
        
        if kind is Action.Kind.RAISE:
            if not isinstance(amount, int):
                type_name = type(amount).__name__
                article = "an" if type_name.startswith(('a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U')) else "a"
                raise TypeError(f"Expected 'amount' to be an int, but it was {article} {type_name}")
            
            if amount <= 0:
                raise ValueError(f"Expected the amount to be greater than 0, but it was {amount}")
            
        elif amount is not None:
            type_name = type(amount).__name__
            article = "an" if type_name.startswith(('a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U')) else "a"
            raise TypeError(f"Expected 'amount' to be a None, but it was {article} {type_name}")
        
        self.amount = amount

    @staticmethod
    def check() -> Action:
        return Action(Action.Kind.CHECK)

    @staticmethod
    def call() -> Action:
        return Action(Action.Kind.CALL)
    
    @staticmethod
    def raise_by(amount: int) -> Action:
        return Action(Action.Kind.RAISE, amount)

    @staticmethod
    def fold() -> Action:
        return Action(Action.Kind.FOLD)

    def __repr__(self):
        match self.kind:
            case self.Kind.CHECK:
                return "Action.check()"
            
            case self.Kind.CALL:
                return "Action.call()"
            
            case self.Kind.RAISE:
                return f"Action.raise_by({self.amount})"
            
            case self.Kind.FOLD:
                return "Action.fold()"

    def __eq__(self, other):
        return self.kind == other.kind and self.amount == other.amount if isinstance(other, Action) else NotImplemented

    def __hash__(self):
        return hash((self.kind, self.amount))
