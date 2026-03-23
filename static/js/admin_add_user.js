(function () {
    var form = document.getElementById("addUserForm");
    var submitBtn = document.getElementById("submitBtn");
    var result = document.getElementById("result");
    var preview = document.getElementById("preview");
    var secretInput = document.getElementById("admin_secret");
    var qrBox = document.getElementById("qrBox");
    var instagramLink = document.getElementById("instagramLink");

    var PROFILE_FIELDS = [
        "full_name",
        "title",
        "services",
        "monthly_turnover_range",
        "yearly_turnover_range",
        "team_size",
        "key_competencies",
        "club_audience_request",
        "hobbies",
        "help_topics",
        "instagram_handle",
        "qr_url"
    ];

    function byId(id) {
        return document.getElementById(id);
    }

    function val(id) {
        var el = byId(id);
        return el ? String(el.value || "").trim() : "";
    }

    function setResult(message, ok) {
        result.className = "result " + (ok ? "ok" : "err");
        result.textContent = message;
    }

    function isChecked(id) {
        var el = byId(id);
        return !!(el && el.checked);
    }

    function buildInstagramUrl(handle) {
        if (!handle) return "";
        var clean = handle.replace(/^@+/, "");
        return clean ? ("https://instagram.com/" + clean) : "";
    }

    function renderPreview(profile) {
        byId("p_full_name").textContent = profile.full_name || "";
        byId("p_title").textContent = profile.title || "";
        byId("p_services").textContent = profile.services || "";

        var turnover = [];
        if (profile.monthly_turnover_range) {
            turnover.push("Monthly: " + profile.monthly_turnover_range);
        }
        if (profile.yearly_turnover_range) {
            turnover.push("Yearly: " + profile.yearly_turnover_range);
        }
        byId("p_turnover").textContent = turnover.join("\n");
        byId("p_team_size").textContent = profile.team_size ? ("Team size: " + profile.team_size) : "";
        byId("p_key_competencies").textContent = profile.key_competencies || "";
        byId("p_club_audience_request").textContent = profile.club_audience_request || "";
        byId("p_hobbies").textContent = profile.hobbies || "";
        byId("p_help_topics").textContent = profile.help_topics || "";

        var qrValue = profile.qr_url || buildInstagramUrl(profile.instagram_handle);
        qrBox.innerHTML = "";
        if (qrValue && window.QRCode) {
            new window.QRCode(qrBox, {
                text: qrValue,
                width: 120,
                height: 120
            });
        } else {
            qrBox.textContent = qrValue || "No QR data";
        }

        var igUrl = buildInstagramUrl(profile.instagram_handle);
        if (igUrl) {
            instagramLink.href = igUrl;
            instagramLink.textContent = igUrl;
            instagramLink.style.display = "inline";
        } else {
            instagramLink.href = "#";
            instagramLink.textContent = "";
            instagramLink.style.display = "none";
        }

        preview.style.display = "grid";
    }

    var storedSecret = localStorage.getItem("admin_secret");
    if (storedSecret && !secretInput.value) {
        secretInput.value = storedSecret;
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        submitBtn.disabled = true;
        setResult("", true);

        try {
            var tgIdRaw = val("tg_id");
            var username = val("username");
            var adminSecret = val("admin_secret");
            if (adminSecret) {
                localStorage.setItem("admin_secret", adminSecret);
            }

            if (!tgIdRaw && !username) {
                throw new Error("Provide at least one identifier: tg_id or username");
            }

            var payload = {
                username: username
            };
            if (tgIdRaw) {
                payload.tg_id = Number(tgIdRaw);
                if (!Number.isFinite(payload.tg_id)) {
                    throw new Error("tg_id must be a valid number");
                }
            }

            PROFILE_FIELDS.forEach(function (key) {
                payload[key] = val(key);
            });
            payload.tags = val("tags");

            var response = await fetch("/admin/users", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Admin-Secret": adminSecret
                },
                body: JSON.stringify(payload)
            });

            var data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || !data.ok) {
                var message = (data && (data.detail || data.error)) || ("Request failed: HTTP " + response.status);
                throw new Error(message);
            }

            var extra = "";
            if (Array.isArray(data.tags) && data.tags.length) {
                extra += " tags=" + data.tags.join(",");
            }
            setResult("User created. user_id=" + data.user_id + (extra ? " " + extra : ""), true);
            renderPreview(data.profile || payload);
        } catch (error) {
            setResult(error.message || "Failed to create user", false);
        } finally {
            submitBtn.disabled = false;
        }
    });
})();
