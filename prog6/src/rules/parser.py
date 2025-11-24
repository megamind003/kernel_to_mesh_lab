import ast
import operator
from typing import Any, Dict


class SafeExpressionParser:
    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.And: operator.and_,
        ast.Or: operator.or_,
        ast.Not: operator.not_,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    def __init__(self):
        self.allowed_names: set[str] = set()

    def parse(self, expression: str) -> ast.Expression:
        try:
            tree = ast.parse(expression, mode='eval')
            return tree
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}")

    def validate_tree(self, node: ast.AST, allowed_names: set[str]) -> None:
        if isinstance(node, ast.Expression):
            self.validate_tree(node.body, allowed_names)
        
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in self.ALLOWED_OPS:
                raise ValueError(f"Operator {type(node.op).__name__} not allowed")
            self.validate_tree(node.left, allowed_names)
            self.validate_tree(node.right, allowed_names)
        
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in self.ALLOWED_OPS:
                raise ValueError(f"Operator {type(node.op).__name__} not allowed")
            self.validate_tree(node.operand, allowed_names)
        
        elif isinstance(node, ast.Compare):
            if any(type(op) not in self.ALLOWED_OPS for op in node.ops):
                raise ValueError("Comparison operator not allowed")
            self.validate_tree(node.left, allowed_names)
            for comparator in node.comparators:
                self.validate_tree(comparator, allowed_names)
        
        elif isinstance(node, ast.BoolOp):
            if type(node.op) not in self.ALLOWED_OPS:
                raise ValueError(f"Boolean operator {type(node.op).__name__} not allowed")
            for value in node.values:
                self.validate_tree(value, allowed_names)
        
        elif isinstance(node, ast.Name):
            if node.id not in allowed_names:
                raise ValueError(f"Variable '{node.id}' not allowed in expression")
        
        elif isinstance(node, (ast.Constant, ast.Num, ast.Str)):
            pass
        
        else:
            raise ValueError(f"AST node type {type(node).__name__} not allowed")

    def evaluate(self, node: ast.AST, context: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body, context)
        
        elif isinstance(node, ast.BinOp):
            left = self.evaluate(node.left, context)
            right = self.evaluate(node.right, context)
            op_func = self.ALLOWED_OPS[type(node.op)]
            return op_func(left, right)
        
        elif isinstance(node, ast.UnaryOp):
            operand = self.evaluate(node.operand, context)
            op_func = self.ALLOWED_OPS[type(node.op)]
            return op_func(operand)
        
        elif isinstance(node, ast.Compare):
            left = self.evaluate(node.left, context)
            
            for op, comparator in zip(node.ops, node.comparators):
                right = self.evaluate(comparator, context)
                op_func = self.ALLOWED_OPS[type(op)]
                
                if not op_func(left, right):
                    return False
                
                left = right
            
            return True
        
        elif isinstance(node, ast.BoolOp):
            op_func = self.ALLOWED_OPS[type(node.op)]
            
            if isinstance(node.op, ast.And):
                return all(self.evaluate(value, context) for value in node.values)
            elif isinstance(node.op, ast.Or):
                return any(self.evaluate(value, context) for value in node.values)
        
        elif isinstance(node, ast.Name):
            if node.id not in context:
                raise ValueError(f"Variable '{node.id}' not found in context")
            return context[node.id]
        
        elif isinstance(node, ast.Constant):
            return node.value
        
        elif isinstance(node, ast.Num):
            return node.n
        
        elif isinstance(node, ast.Str):
            return node.s
        
        else:
            raise ValueError(f"Cannot evaluate node type {type(node).__name__}")

    def safe_eval(self, expression: str, context: Dict[str, Any]) -> Any:
        tree = self.parse(expression)
        
        allowed_names = set(context.keys())
        self.validate_tree(tree, allowed_names)
        
        result = self.evaluate(tree, context)
        
        return result
