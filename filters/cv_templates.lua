local stringify = pandoc.utils.stringify

local function escape_html(text)
  return text
    :gsub("&", "&amp;")
    :gsub("<", "&lt;")
    :gsub(">", "&gt;")
    :gsub('"', "&quot;")
end

local function slugify(text)
  local slug = text:lower()
  slug = slug:gsub("[^%w]+", "_")
  slug = slug:gsub("^_+", "")
  slug = slug:gsub("_+$", "")
  return slug
end

local function meta_string(value, default)
  if value == nil then
    return default or ""
  end
  local text = stringify(value)
  if text == "" then
    return default or ""
  end
  return text
end

local function meta_list(value)
  if value == nil then
    return {}
  end
  if value.t == "MetaList" then
    local items = {}
    for _, item in ipairs(value) do
      table.insert(items, stringify(item))
    end
    return items
  end
  if type(value) == "table" and #value > 0 then
    local items = {}
    for _, item in ipairs(value) do
      table.insert(items, stringify(item))
    end
    return items
  end
  return { stringify(value) }
end

local function generated_date()
  local value = os.date("%B %d, %Y")
  return value:gsub("(%a+) 0(%d, %d%d%d%d)", "%1 %2")
end

local function derived_href(kind, value)
  if value == nil or value == "" then
    return ""
  end

  if kind == "phone" then
    local digits = value:gsub("[^%d+]", "")
    if digits:match("^%d%d%d%d%d%d%d%d%d%d$") then
      digits = "+1" .. digits
    end
    if not digits:match("^%+") and digits:match("^1%d%d%d%d%d%d%d%d%d%d$") then
      digits = "+" .. digits
    end
    return "tel:" .. digits
  end

  if kind == "email" then
    return "mailto:" .. value
  end

  if kind == "website" then
    if value:match("^https?://") then
      return value
    end
    return "https://" .. value
  end

  if kind == "orcid" then
    if value:match("^https?://") then
      return value
    end
    return "https://orcid.org/" .. value
  end

  if kind == "scholar" then
    if value:match("^https?://") then
      return value
    end
    return "https://scholar.google.com/citations?user=" .. value
  end

  if kind == "github" then
    if value:match("^https?://") then
      return value
    end
    return "https://github.com/" .. value
  end

  return value
end

local function is_html_comment(block)
  return block.t == "RawBlock"
    and block.format == "html"
    and block.text:match("^<!%-%-")
end

local function collect_sections(blocks)
  local sections = {}
  local current = nil
  local pending_tex = nil
  local pending_grants = false
  local pending_full = false

  for _, block in ipairs(blocks) do
    if is_html_comment(block) then
      -- Metadata comments in section source are for generators only,
      -- except an optional "tex: <path>" override naming the generated
      -- .tex file for the section that follows (used when the source
      -- filename differs from the slugified section title).
      local override = block.text:match("tex:%s*(%S+)")
      if override then
        pending_tex = override
      end
      if block.text:match("type:%s*grants") then
        pending_grants = true
      end
      if block.text:match("detail:%s*full") then
        pending_full = true
      end
    elseif block.t == "Header" and block.level == 2 then
      if current then
        table.insert(sections, current)
      end
      current = {
        title = stringify(block.content),
        blocks = { block },
        tex = pending_tex,
        grants = pending_grants,
        full = pending_full,
      }
      pending_tex = nil
      pending_grants = false
      pending_full = false
    elseif current then
      table.insert(current.blocks, block)
    end
  end

  if current then
    table.insert(sections, current)
  end

  return sections
end

-- Per-document section controls from the "cv-sections" front matter:
--   retitle: {"<section title>": "<display title>", ...}
--   demote:  ["<section title>", ...]  -- rendered as a group under the
--                                       -- category heading that precedes it
local function section_controls(meta)
  local cfg = meta["cv-sections"] or {}
  local retitle = {}
  if cfg.retitle then
    for key, value in pairs(cfg.retitle) do
      retitle[key] = stringify(value)
    end
  end
  local demote = {}
  for _, name in ipairs(meta_list(cfg.demote)) do
    demote[name] = true
  end
  return retitle, demote
end

local function sorted_keys(tbl)
  local keys = {}
  for key in pairs(tbl) do
    table.insert(keys, key)
  end
  table.sort(keys)
  return keys
end

-- A section written as a bare "## Heading" in the .qmd with nothing under
-- it: a category heading that groups the demoted sections following it.
local function is_heading_only(section)
  return #section.blocks == 1
end

local function shift_headers(blocks)
  local shifted = {}
  for _, block in ipairs(blocks) do
    if block.t == "Header" then
      table.insert(shifted, pandoc.Header(math.min(block.level + 1, 6), block.content, block.attr))
    else
      table.insert(shifted, block)
    end
  end
  return shifted
end

-- Grant entries can carry extra detail: the credit share after the role
-- ("Co-PI (50%).") and a trailing "Investigators: ..." sentence. The PDF build
-- gets brief .tex files from build_sections.py; the HTML build reads the
-- source Markdown, so the same detail is dropped here unless the section is
-- marked "detail: full" (the generated _full sections).
local function strip_grant_detail(inlines)
  local out = {}
  for _, el in ipairs(inlines) do
    if el.t == "Str" and el.text == "Investigators:" then
      if #out > 0 and out[#out].t == "Space" then
        table.remove(out)
      end
      break
    elseif el.t == "Str" and el.text:match("^%(%d+%%%)[%.,;]?$") then
      local punct = el.text:match("([%.,;]?)$")
      if #out > 0 and out[#out].t == "Space" then
        table.remove(out)
      end
      if punct ~= "" then
        if #out > 0 and out[#out].t == "Str" then
          out[#out] = pandoc.Str(out[#out].text .. punct)
        else
          table.insert(out, pandoc.Str(punct))
        end
      end
    else
      table.insert(out, el)
    end
  end
  return out
end

local function brief_grant_blocks(blocks)
  local result = {}
  for _, block in ipairs(blocks) do
    if block.t == "BulletList" or block.t == "OrderedList" then
      local items = {}
      for _, item in ipairs(block.content) do
        local new_item = {}
        for _, b in ipairs(item) do
          if b.t == "Para" or b.t == "Plain" then
            b = pandoc[b.t](strip_grant_detail(b.content))
          end
          table.insert(new_item, b)
        end
        table.insert(items, new_item)
      end
      block = block.t == "BulletList" and pandoc.BulletList(items) or pandoc.OrderedList(items, block.listAttributes)
    end
    table.insert(result, block)
  end
  return result
end

local function html_header(meta)
  local cv = meta.cv or {}
  local name = meta_string(cv.name, meta_string(meta.author, meta_string(meta.title, "Curriculum Vitae")))

  local phone = meta_string(cv.phone, "")
  local phone_href = derived_href("phone", phone)
  local email = meta_string(cv.email, "")
  local email_href = derived_href("email", email)
  local website = meta_string(cv.website, "")
  local website_label = meta_string(cv["website-label"], website)
  local website_href = derived_href("website", website)
  local orcid = meta_string(cv.orcid, "")
  local orcid_href = derived_href("orcid", orcid)
  local scholar = meta_string(cv.scholar, "")
  local scholar_href = derived_href("scholar", scholar)
  local github = meta_string(cv.github, "")
  local github_href = derived_href("github", github)
  local address_lines = {}
  for _, line in ipairs(meta_list(cv.address)) do
    table.insert(
      address_lines,
      '<span class="cv-address-line">' .. escape_html(line) .. "</span>"
    )
  end
  local address = table.concat(address_lines, "\n")
  local generated = generated_date()

  local function link(href, class_name, label)
    if href == "" or label == "" then
      return ""
    end
    return string.format(
      '<a href="%s" class="%s">%s</a>',
      escape_html(href),
      class_name,
      escape_html(label)
    )
  end

  local function stack(items)
    local present = {}
    for _, item in ipairs(items) do
      if item ~= "" then
        table.insert(present, item)
      end
    end
    return table.concat(present, "<br>")
  end

  return table.concat({
    '<p><a href="#main-content" class="skip-link">Skip to main content</a></p>',
    '<div class="cv-page">',
    '<div class="cv-header">',
    '<div class="cv-name-block">',
    '<div class="cv-name-row">',
    '<div class="cv-name-title"><p>' .. escape_html(name) .. '</p></div>',
    '<div class="cv-name-actions">',
    '<p>',
    '<a href="#" class="cv-header-action js-expand-all">Expand all</a> ',
    '<a href="#" class="cv-header-action js-collapse-all">Collapse all</a> ',
    '<a href="#" class="cv-header-action js-print">Print to PDF</a>',
    '</p>',
    '</div>',
    '</div>',
    '</div>',
    '<div class="cv-header-grid">',
    '<div class="cv-header__column"><div class="cv-header__stack"><p>',
    stack({
      link(phone_href, "cv-header-link cv-header-link--phone", phone),
      link(email_href, "cv-header-link cv-header-link--email", email),
      link(website_href, "cv-header-link cv-header-link--web", website_label),
      '<span class="cv-header-date">Generated ' .. escape_html(generated) .. '</span>',
    }),
    '</p></div></div>',
    '<div class="cv-header__column"><div class="cv-header__stack"><p>',
    stack({
      link(orcid_href, "cv-header-link cv-header-link--orcid", "ORCID"),
      link(scholar_href, "cv-header-link cv-header-link--scholar", "Google Scholar"),
      link(github_href, "cv-header-link cv-header-link--github", github),
    }),
    '</p></div></div>',
    '<div class="cv-header__column"><div class="cv-address">' .. address .. '</div></div>',
    '</div>',
    '</div>',
    '<div id="main-content" class="cv-main">',
  }, "\n")
end

local function latex_command_for(title, tex_override)
  if tex_override then
    -- "input:<path>" loads a free-form LaTeX file; a bare path is a rubric table.
    local input_path = tex_override:match("^input:(.+)$")
    if input_path then
      return "\\input{" .. input_path .. "}"
    end
    return "\\makerubric{" .. tex_override .. "}"
  end

  local explicit = {
    ["Awards and Honors"] = "\\makerubric{generated/tex/awards}",
    ["Invited Conference Talks"] = "\\makerubric{generated/tex/conference_talks}",
    ["Invited Seminar Talks"] = "\\makerubric{generated/tex/seminar_talks}",
    ["Contributed Conference Talks"] = "\\makerubric{generated/tex/contributed_talks}",
    ["Contributed Conference Talks and Posters"] = "\\makerubric{generated/tex/contributed_talks}",
    ["Co-authored Conference Presentations"] = "\\makerubric{generated/tex/co_authored_presentations}",
    ["Academic Service"] = "\\makerubric{generated/tex/service_academic}",
    ["Professional Service"] = "\\makerubric{generated/tex/service_professional}",
    -- "Selected Publications" needs no entry here: every generated selection
    -- carries its own "tex: input:..." override (see publications/selections.json).
    ["Publications"] = "\\input{publications/publications}",
    ["Grants Pending"] = "\\makerubric{generated/tex/grants/pending}",
    ["Grants Awarded"] = "\\makerubric{generated/tex/grants/awarded}",
    ["Grants Active"] = "\\makerubric{generated/tex/grants/active}",
    ["Grants Awarded but Declined"] = "\\makerubric{generated/tex/grants/declined}",
    ["Grants Not Awarded"] = "\\makerubric{generated/tex/grants/not_awarded}",
    ["Selected Grants"] = "\\makerubric{generated/tex/grants_short}",
    ["Students Advised"] = "\\makerubric{generated/tex/students_short}",
  }

  if explicit[title] then
    return explicit[title]
  end

  return "\\makerubric{generated/tex/" .. slugify(title) .. "}"
end

local function render_html(doc)
  local retitle, demote = section_controls(doc.meta)
  local sections = collect_sections(doc.blocks)
  local blocks = {
    pandoc.RawBlock("html", html_header(doc.meta)),
  }

  -- Each group becomes one .cv-section div with exactly one h2 (the JS
  -- builds the collapse toggle from it); demoted sections merge into the
  -- preceding group with their headings shifted down one level.
  local groups = {}
  for _, section in ipairs(sections) do
    local content = section.blocks
    if section.grants and not section.full then
      content = brief_grant_blocks(content)
    end
    if retitle[section.title] then
      local header = content[1]
      content[1] = pandoc.Header(header.level, { pandoc.Str(retitle[section.title]) }, header.attr)
    end
    if demote[section.title] and #groups > 0 then
      local parent = groups[#groups]
      for _, block in ipairs(shift_headers(content)) do
        table.insert(parent.blocks, block)
      end
    else
      table.insert(groups, { title = section.title, blocks = content })
    end
  end

  for _, group in ipairs(groups) do
    local class_name = group.title == "Publications" and "publications-section" or "cv-section"
    table.insert(blocks, pandoc.Div(group.blocks, pandoc.Attr("", { class_name })))
  end

  table.insert(blocks, pandoc.RawBlock("html", "</div>\n</div>"))
  return pandoc.Pandoc(blocks, doc.meta)
end

local function render_latex(doc)
  local cv_latex = doc.meta["cv-latex"] or {}
  local spacing_parts = {}
  for _, key in ipairs({"rubricafterspace", "rubricspace", "subrubricspace"}) do
    local val = meta_string(cv_latex[key], "")
    if val ~= "" then
      table.insert(spacing_parts, "\\setlength{\\" .. key .. "}{" .. val .. "}")
    end
  end

  local sections = collect_sections(doc.blocks)
  local blocks = {}

  if meta_string(cv_latex.compactheader, "") == "true" then
    table.insert(blocks, pandoc.RawBlock("latex", "\\CVcompactheadertrue"))
  end
  for _, key in ipairs({"maxnames", "minnames"}) do
    local value = meta_string(cv_latex[key], "")
    if value:match("^%d+$") then
      table.insert(blocks, pandoc.RawBlock("latex", "\\renewcommand{\\CVbib" .. key .. "}{" .. value .. "}"))
    end
  end
  table.insert(blocks, pandoc.RawBlock("latex", "\\makeheaders[c]"))

  if #spacing_parts > 0 then
    table.insert(blocks, pandoc.RawBlock("latex", table.concat(spacing_parts, "\n")))
  end

  if meta_string(cv_latex.studentmarkers, "") == "true" then
    table.insert(blocks, pandoc.RawBlock("latex", "\\toggletrue{studentmarkers}"))
  end

  local retitle, demote = section_controls(doc.meta)
  for _, key in ipairs(sorted_keys(retitle)) do
    table.insert(blocks, pandoc.RawBlock("latex", "\\CVretitle{" .. key .. "}{" .. retitle[key] .. "}"))
  end

  doc.meta.title = pandoc.MetaString("")
  doc.meta.subtitle = pandoc.MetaString("")
  doc.meta.author = pandoc.MetaList({})

  for _, section in ipairs(sections) do
    local command
    if is_heading_only(section) then
      -- Category heading with no table of its own; keep it with what follows.
      command = "\\makerubrichead{" .. section.title .. "}\\par\\nopagebreak"
    else
      command = latex_command_for(section.title, section.tex)
      if demote[section.title] then
        command = "\\CVdemoted{" .. command .. "}"
      end
    end
    table.insert(blocks, pandoc.RawBlock("latex", command))
    for _, block in ipairs(section.blocks) do
      if block.t == "RawBlock" and (block.format == "latex" or block.format == "tex") then
        table.insert(blocks, block)
      end
    end
  end

  return pandoc.Pandoc(blocks, doc.meta)
end

function Pandoc(doc)
  if FORMAT:match("html") then
    return render_html(doc)
  end

  if FORMAT:match("latex") then
    return render_latex(doc)
  end

  return doc
end
