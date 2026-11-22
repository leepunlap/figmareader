#!/usr/bin/env swift
// fgclick — post real mouse events to the frontmost app (CoreGraphics).
//
// System Events `click at` does not reach Chromium/Figma canvas content, so this
// posts genuine CGEvent mouse down/up pairs at global display coordinates
// (points, matching the AX coordinate space and the macOS screencapture space
// divided by the display scale factor).
//
// Usage:
//   fgclick <x> <y> [shift|cmd|alt|ctrl]      click at x,y
//   fgclick drag <x1> <y1> <x2> <y2> [mod]    press at x1,y1, drag, release at x2,y2
//   fgclick move <x> <y>                      move the pointer only
//   fgclick double <x> <y>                    double click

import Foundation
import CoreGraphics

func flags(_ name: String?) -> CGEventFlags {
    switch name {
    case "shift": return .maskShift
    case "cmd", "command": return .maskCommand
    case "alt", "option": return .maskAlternate
    case "ctrl", "control": return .maskControl
    default: return []
    }
}

func post(_ type: CGEventType, _ x: Double, _ y: Double, _ f: CGEventFlags) {
    guard let ev = CGEvent(mouseEventSource: nil,
                           mouseType: type,
                           mouseCursorPosition: CGPoint(x: x, y: y),
                           mouseButton: .left) else { return }
    ev.flags = f
    ev.post(tap: .cghidEventTap)
}

func postRight(_ type: CGEventType, _ x: Double, _ y: Double) {
    guard let ev = CGEvent(mouseEventSource: nil,
                           mouseType: type,
                           mouseCursorPosition: CGPoint(x: x, y: y),
                           mouseButton: .right) else { return }
    ev.post(tap: .cghidEventTap)
}

// Chromium ignores the flag bits on a synthetic mouse event unless the modifier
// key is also physically held down, so post real key down/up around the click.
func modifierKey(_ name: String?) -> (UInt16, CGEventFlags)? {
    switch name {
    case "shift": return (0x38, .maskShift)
    case "cmd", "command": return (0x37, .maskCommand)
    case "alt", "option": return (0x3A, .maskAlternate)
    case "ctrl", "control": return (0x3B, .maskControl)
    default: return nil
    }
}

func keyDown(_ code: UInt16) {
    CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true)?.post(tap: .cghidEventTap)
}

func keyUp(_ code: UInt16) {
    CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false)?.post(tap: .cghidEventTap)
}

let a = Array(CommandLine.arguments.dropFirst())
guard !a.isEmpty else {
    print("usage: fgclick <x> <y> [mod] | drag x1 y1 x2 y2 | move x y | double x y")
    exit(1)
}

switch a[0] {
case "right":
    guard a.count >= 3 else { exit(1) }
    let x = Double(a[1])!, y = Double(a[2])!
    post(.mouseMoved, x, y, [])
    usleep(60_000)
    postRight(.rightMouseDown, x, y)
    usleep(70_000)
    postRight(.rightMouseUp, x, y)

case "scroll":
    guard a.count >= 4 else { exit(1) }
    let x = Double(a[1])!, y = Double(a[2])!, dy = Double(a[3])!
    post(.mouseMoved, x, y, [])
    usleep(60_000)
    let ev = CGEvent(scrollWheelEvent2Source: nil, units: .pixel, wheelCount: 1, wheel1: Int32(dy), wheel2: 0, wheel3: 0)
    ev?.post(tap: .cghidEventTap)

case "drag":
    guard a.count >= 5 else { exit(1) }
    let x1 = Double(a[1])!, y1 = Double(a[2])!, x2 = Double(a[3])!, y2 = Double(a[4])!
    let f = flags(a.count > 5 ? a[5] : nil)
    post(.mouseMoved, x1, y1, f)
    usleep(60_000)
    post(.leftMouseDown, x1, y1, f)
    let steps = 24
    for i in 1...steps {
        let t = Double(i) / Double(steps)
        post(.mouseMoved, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, f)
        usleep(8_000)
    }
    usleep(60_000)
    post(.leftMouseUp, x2, y2, f)

case "move":
    guard a.count >= 3 else { exit(1) }
    post(.mouseMoved, Double(a[1])!, Double(a[2])!, [])

case "double":
    guard a.count >= 3 else { exit(1) }
    let x = Double(a[1])!, y = Double(a[2])!
    let f = flags(a.count > 3 ? a[3] : nil)
    post(.mouseMoved, x, y, f)
    usleep(50_000)
    post(.leftMouseDown, x, y, f)
    post(.leftMouseUp, x, y, f)
    usleep(60_000)
    post(.leftMouseDown, x, y, f)
    post(.leftMouseUp, x, y, f)

default:
    guard a.count >= 2 else { exit(1) }
    let x = Double(a[0])!, y = Double(a[1])!
    let mod = modifierKey(a.count > 2 ? a[2] : nil)
    if let m = mod { keyDown(m.0) }
    usleep(40_000)
    post(.mouseMoved, x, y, mod?.1 ?? [])
    usleep(50_000)
    post(.leftMouseDown, x, y, mod?.1 ?? [])
    usleep(60_000)
    post(.leftMouseUp, x, y, mod?.1 ?? [])
    usleep(40_000)
    if let m = mod { keyUp(m.0) }
}

usleep(80_000)
