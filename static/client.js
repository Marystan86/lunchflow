// // static\client.js

import * as utils from './utils.js';
import * as geo from './geo-and-session.js';
import * as ui from './ui-and-screens.js?v=20260315c';
import { initDevUserSwitcher } from "./js/dev-user-switcher.js";

document.addEventListener("DOMContentLoaded", () => {
  initDevUserSwitcher().catch((error) => {
    console.warn("dev user switcher init failed", error);
  });
});
