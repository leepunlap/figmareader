#!/usr/bin/env swift
// fgkey — post real keyboard events to the frontmost app (CoreGraphics).
//
//   fgkey <key>            press key (e.g. "1", "a", "escape", "return")
//   fgkey shift+1          press with modifiers
//   fgkey cmd+shift+h
//
// Key names: a-z, 0-9, "return", "tab", "escape", "space", "up", "down",
// "left", "right", "f1".."f12", "slash", "comma", "period", "minus".

import Foundation
import CoreGraphics

func keyCode(_ name: String) -> CGKeyCode? {
    let map: [String: CGKeyCode] = [
        "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4,
        "i": 34, "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31,
        "p": 35, "q": 12, "r": 15, "s": 1, "t": 17, "u": 32, "v": 9,
        "w": 13, "x": 7, "y": 16, "z": 6,
        "0": 29, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22,
        "7": 26, "8": 28, "9": 24,
        "return": 36, "enter": 36, "tab": 48, "escape": 53, "esc": 53,
        "space": 49, "up": 126, "down": 125, "left": 123, "right": 124,
        "slash": 41, "comma": 43, "period": 47, "minus": 27, "equal": 24,
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
        "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
        "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
        "delete": 117, "backspace": 51,
    ]
    return map[name.lowercased()]
}

func flagFor(_ name: String) -> CGEventFlags {
    switch name {
    case "shift": return .maskShift
    case "cmd", "command": return .maskCommand
    case "alt", "option": return .maskAlternate
    case "ctrl", "control": return .maskControl
    default: return []
    }
}

let raw = Array(CommandLine.arguments.dropFirst())
guard !raw.isEmpty else {
    print("usage: fgkey <key> [modifiers...]")
    exit(1)
}

var modifiers: [String] = []
var keyName = raw[0].lowercased()
for a in raw {
    if a.contains("+") {
        let parts = a.lowercased().split(separator: "+").map(String.init)
        keyName = parts.last ?? keyName
        modifiers.append(contentsOf: parts.dropLast())
    }
}

guard let code = keyCode(keyName) else {
    print("unknown key '\(keyName)'")
    exit(2)
}

var flags: CGEventFlags = []
for m in modifiers { flags.insert(flagFor(m)) }

func post(_ type: CGEventType, _ code: CGKeyCode, _ flags: CGEventFlags) {
    guard let ev = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: type == .keyDown) else { return }
    ev.flags = flags
    ev.post(tap: .cghidEventTap)
}

// hold modifier keys down while the main key is pressed
for m in ["cmd", "ctrl", "alt", "shift"] where modifiers.contains(m) {
    let mc: CGKeyCode = m == "cmd" ? 55 : (m == "ctrl" ? 59 : (m == "alt" ? 58 : 56))
    post(.keyDown, mc, [])
    usleep(40_000)
}
post(.keyDown, code, flags)
usleep(60_000)
post(.keyUp, code, flags)
for m in ["shift", "alt", "ctrl", "cmd"].reversed() where modifiers.contains(m) {
    let mc: CGKeyCode = m == "cmd" ? 55 : (m == "ctrl" ? 59 : (m == "alt" ? 58 : 56))
    post(.keyUp, mc, [])
    usleep(40_000)
}
print("key '\(keyName)' \(flags.rawValue)")
