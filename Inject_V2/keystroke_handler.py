"""Keystroke handler - extracted from inject_v3.py"""
import json
import os
import re


class KeystrokeHandler:
    """Manages keyboard shortcuts from names.json."""
    
    def __init__(self, browser_controller, names_file=None):
        """Initialize keystroke handler with browser controller and optional names file path."""
        self.browser = browser_controller
        self.names_file = names_file
        self.shortcuts = {}
        self.names_list = []  # Store original names list for UI
        self._load_shortcuts()
    
    def _load_shortcuts(self):
        """Load shortcuts from names.json and register defaults."""
        # Register default navigation shortcuts
        self.shortcuts['n'] = ('next', None)
        self.shortcuts['N'] = ('next', None)
        self.shortcuts['p'] = ('prev', None)
        self.shortcuts['P'] = ('prev', None)
        
        # Register space/add shortcuts
        self.shortcuts['a'] = ('space', None)
        self.shortcuts['A'] = ('space', None)
        self.shortcuts[' '] = ('space', None)
        
        # Load names from names.json
        names = self._load_names()
        self.names_list = names  # Store for UI
        
        for raw in names:
            label = raw
            pushed = ''.join(ch for ch in raw if ch not in '()')
            
            match = re.search(r'\((.)\)', label)
            if match:
                shortcut_key = match.group(1)
                # Single letter shortcuts
                self.shortcuts[shortcut_key.lower()] = ('name', pushed)
                self.shortcuts[shortcut_key.upper()] = ('name', pushed)
                # Ctrl+letter shortcuts for consistency
                self.shortcuts[(shortcut_key.lower(), 'ctrl')] = ('name', pushed)
                self.shortcuts[(shortcut_key.upper(), 'ctrl')] = ('name', pushed)
                print(f'[KEYSTROKE] Registered shortcut: {shortcut_key} -> {pushed}')
                print(f'[KEYSTROKE] Registered Ctrl+{shortcut_key} -> {pushed}')
            
            # Extract numbered groups like "(1) Dennis Laura "
            num_match = re.search(r'\((\d+)\)', label)
            if num_match:
                group_num = num_match.group(1)
                # Register Ctrl+number for numbered groups
                self.shortcuts[(group_num, 'ctrl')] = ('name', pushed)
                print(f'[KEYSTROKE] Registered Ctrl+{group_num} -> {pushed}')
    
    def _load_names(self):
        """Load names from names.json file."""
        names = []
        
        # Try provided path first
        if self.names_file and os.path.exists(self.names_file):
            try:
                with open(self.names_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        names = data.get('names', [])
                    elif isinstance(data, list):
                        names = data
                    print(f'[KEYSTROKE] Loaded {len(names)} names from {self.names_file}')
                    return names
            except Exception as e:
                print(f'[KEYSTROKE] Failed to load {self.names_file}: {e}')
        
        # Try standard locations
        ROOT = os.path.dirname(__file__)
        paths_to_try = [
            os.path.join(ROOT, 'names.json'),
            os.path.join(ROOT, '..', 'poc', 'names.json'),
        ]
        
        for path in paths_to_try:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            names = data.get('names', [])
                        elif isinstance(data, list):
                            names = data
                        if names:
                            print(f'[KEYSTROKE] Loaded {len(names)} names from {path}')
                            return names
                except Exception as e:
                    print(f'[KEYSTROKE] Failed to load {path}: {e}')
        
        # Fallback
        print('[KEYSTROKE] Using fallback names')
        names = ['(D)ennis', '(L)aura', '(B)ekah']
        return names
    
    def on_key_press(self, key, ctrl=False, state=0):
        """Handle key press event and return action tuple or None.
        
        Args:
            key: The key character or name (e.g., '1', 'd', 'BackSpace', 'Delete')
            ctrl: Boolean indicating if Ctrl modifier is pressed
            state: Raw event state bitmask for detecting Fn+Delete on Mac
        
        Returns:
            Tuple of (action_type, action_data) or None
        """
        # Try direct lookup first
        if key in self.shortcuts:
            return self.shortcuts[key]
        
        # Try Ctrl+ combination
        if ctrl:
            ctrl_key = (key, 'ctrl')
            if ctrl_key in self.shortcuts:
                return self.shortcuts[ctrl_key]
        
        # Handle Delete key variants
        if key == 'Delete':
            # Fn+Delete (state=0x40 on Mac) = clear entire description
            if state & 0x40:
                print('[DELETE_TYPE] Fn+Delete detected - clearing entire description')
                return ('delete_all', None)
            # Ctrl+Delete or Shift+Delete = delete 50 chars from end
            elif ctrl or (state & 0x01):  # 0x01 is Shift
                print('[DELETE_TYPE] Ctrl/Shift+Delete detected - deleting 50 chars')
                return ('delete_50', None)
            # Plain Delete = delete previous character
            else:
                print('[DELETE_TYPE] Plain Delete detected - deleting one char')
                return ('backspace', None)
        
        # Check for backspace key 'x' or 'X'
        if key.lower() == 'x':
            return ('backspace', None)
        
        return None
    
    def get_all_shortcuts(self):
        """Return dict of all registered shortcuts."""
        return self.shortcuts.copy()
    
    def get_names_list(self):
        """Return original names list for UI button creation."""
        return self.names_list.copy()
