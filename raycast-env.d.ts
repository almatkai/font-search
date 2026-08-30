/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Preview Text - Text to use for font preview */
  "previewText": string
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `search-fonts` command */
  export type SearchFonts = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `search-fonts` command */
  export type SearchFonts = {}
}

