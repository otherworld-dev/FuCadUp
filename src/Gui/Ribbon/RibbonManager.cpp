/***************************************************************************
 *   Copyright (c) 2026 FuCad contributors                                 *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 ***************************************************************************/


#include <algorithm>
#include <cstddef>
#include <utility>

#include <QAction>
#include <QByteArray>
#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QJsonValue>
#include <QList>
#include <QMenu>
#include <QTimer>
#include <QWidget>

#include <App/Application.h>
#include <Base/Console.h>
#include <Base/Interpreter.h>
#include <Base/Parameter.h>
#include <Base/Tools.h>
#include <Gui/Action.h>
#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/MainWindow.h>
#include <Gui/ToolBarManager.h>
#include <Gui/WorkbenchManager.h>

#include "RibbonBar.h"
#include "RibbonButton.h"
#include "RibbonManager.h"
#include "RibbonPage.h"
#include "RibbonPanel.h"
#include "RibbonPanelMenu.h"


using namespace Gui;
using namespace Gui::Ribbon;

namespace
{
const char* const workspaceResource = ":/ribbon/Workspaces/Design.json";
const char* const mainWindowPreferences = "User parameter:BaseApp/Preferences/MainWindow";
// One group per tab, one per panel under it, holding the row the user arranged.
const char* const preferencesPath = "User parameter:BaseApp/Preferences";
const char* const ribbonGroupName = "Ribbon";
const char* const panelsGroupName = "Panels";
const char* const panelLayoutPreferences = "User parameter:BaseApp/Preferences/Ribbon/Panels";
const char* const rowKey = "Row";
const QLatin1Char rowSeparator(';');
const QLatin1Char keySeparator('/');

/**
 * The parameter group name for \a key. ParameterGrp reads a slash as a path
 * separator, so a toolbar named with one has to be stored under a name without.
 */
QByteArray parameterName(const QString& key)
{
    QString safe = key;
    safe.replace(keySeparator, QLatin1Char('|'));
    return safe.toUtf8();
}

// The toolbars StdWorkbench::setupToolBars() gives every workbench. They stay
// off a generated tab: the app bar's menus carry their commands, the workspace
// selector at the head of every page is the Workbench toolbar, and the tabs
// the workspace definition describes do not repeat them either.
const QStringList standardToolBars = {
    QStringLiteral("File"),
    QStringLiteral("Edit"),
    QStringLiteral("Clipboard"),
    QStringLiteral("Workbench"),
    QStringLiteral("Macro"),
    QStringLiteral("View"),
    QStringLiteral("Individual Views"),
    QStringLiteral("Structure"),
    QStringLiteral("Help"),
};

/// The command framework action of \a command, or nullptr when not registered.
Gui::Action* resolveGuiAction(const QString& command)
{
    if (command.isEmpty() || !Application::Instance) {
        return nullptr;
    }

    CommandManager& manager = Application::Instance->commandManager();
    Command* cmd = manager.getCommandByName(command.toLatin1().constData());
    if (!cmd) {
        return nullptr;
    }

    cmd->initAction();
    return cmd->getAction();
}

/**
 * The Fusion wording of \a text in the running language.
 *
 * The workspace definition is data rather than source, so lupdate cannot find
 * its captions; they are looked up under the "Ribbon" context, which is where a
 * translator adds the strings of Workspaces/Design.json. A lookup that finds
 * nothing returns the source string, so an English build is unaffected.
 */
QString translateRibbon(const QString& text)
{
    if (text.isEmpty()) {
        return text;
    }

    return QCoreApplication::translate("Ribbon", text.toUtf8().constData());
}

void reportMissing(const QString& command, bool quiet)
{
    if (quiet) {
        Base::Console().log(
            "Ribbon: '%s' is not available, its module is not loaded\n",
            command.toUtf8().constData()
        );
        return;
    }

    Base::Console().warning(
        "Ribbon: skipping unknown command '%s'\n",
        command.toUtf8().constData()
    );
}

}  // namespace


RibbonManager* RibbonManager::_instance = nullptr;

RibbonManager::RibbonManager() = default;

RibbonManager::~RibbonManager() = default;

RibbonManager* RibbonManager::instance()
{
    if (!_instance) {
        _instance = new RibbonManager();
    }

    return _instance;
}

void RibbonManager::destruct()
{
    delete _instance;
    _instance = nullptr;
}

bool RibbonManager::isEnabled()
{
    // Sampled once: the shell is installed while the main window is built, so a
    // later change cannot take effect and the toolbars must keep matching the
    // shell that was actually installed.
    static const bool enabled = App::GetApplication()
                                    .GetParameterGroupByPath(mainWindowPreferences)
                                    ->GetBool("UseRibbon", true);
    return enabled;
}

void RibbonManager::attach(RibbonBar* bar)
{
    ribbonBar = bar;
    if (!bar) {
        return;
    }

    connect(bar, &RibbonBar::tabActivated, this, &RibbonManager::onTabActivated);

    if (MainWindow* window = getMainWindow()) {
        connect(window, &MainWindow::workbenchActivated, this, &RibbonManager::onWorkbenchActivated);
    }

    const std::string active = WorkbenchManager::instance()->activeName();
    if (!active.empty()) {
        rebuildTabs(QString::fromStdString(active));
    }
}

void RibbonManager::rememberToolBars(const QString& workbench, const ToolBarItem* toolBars)
{
    if (workbench.isEmpty() || !toolBars) {
        return;
    }

    std::vector<PanelDefinition> panels;

    const QList<ToolBarItem*> bars = toolBars->getItems();
    for (const ToolBarItem* bar : bars) {
        if (!bar) {
            continue;
        }

        const QString name = QString::fromStdString(bar->command());
        if (standardToolBars.contains(name)) {
            continue;
        }

        PanelDefinition panel;
        // The name is the key the user's layout is stored under; what the
        // caption shows is the translation the toolbar itself would carry.
        panel.caption = name;
        panel.displayCaption = QCoreApplication::translate("Workbench", bar->command().c_str());

        const QList<ToolBarItem*> entries = bar->getItems();
        for (const ToolBarItem* entry : entries) {
            if (!entry) {
                continue;
            }

            const QString command = QString::fromStdString(entry->command());
            if (command.isEmpty() || command == QLatin1String("Separator")) {
                continue;
            }

            ItemDefinition item;
            item.command = command;
            panel.items.push_back(std::move(item));
        }

        if (!panel.items.empty()) {
            panels.push_back(std::move(panel));
        }
    }

    rememberedToolBars[workbench] = std::move(panels);
}

void RibbonManager::resetPanelArrangements()
{
    clearAllRowOverrides();
    scheduleAllPagesRebuild();
}

void RibbonManager::pushContextTab(const QString& id)
{
    if (ribbonBar.isNull()) {
        return;
    }

    loadWorkspace();

    const TabDefinition* definition = findContextTab(id);
    if (!definition) {
        Base::Console().warning(
            "Ribbon: the workspace definition describes no context tab '%s'\n",
            id.toUtf8().constData()
        );
        return;
    }

    for (const ContextTabState& state : activeContextTabs) {
        if (state.tab == definition) {
            const int shown = indexOfTab(definition);
            if (shown >= 0) {
                Base::StateLocker lock(updating);
                ribbonBar->setCurrentIndex(shown);
            }

            buildPage(shown);
            return;
        }
    }

    ContextTabState state;
    state.tab = definition;

    const int current = ribbonBar->currentIndex();
    if (current >= 0 && current < static_cast<int>(visibleTabs.size())) {
        state.restore = visibleTabs[current]->id;
    }

    activeContextTabs.push_back(state);

    int index = -1;
    {
        Base::StateLocker lock(updating);

        visibleTabs.push_back(definition);
        pageBuilt.push_back(false);

        index = ribbonBar->addTab(translateRibbon(definition->id));
        ribbonBar->setContextTabPresent(true);
        ribbonBar->setCurrentIndex(index);
    }

    buildPage(index);
}

void RibbonManager::popContextTab(const QString& id)
{
    if (ribbonBar.isNull()) {
        return;
    }

    auto state = activeContextTabs.end();
    for (auto it = activeContextTabs.begin(); it != activeContextTabs.end(); ++it) {
        if (it->tab->id == id) {
            state = it;
            break;
        }
    }

    if (state == activeContextTabs.end()) {
        return;
    }

    const TabDefinition* definition = state->tab;
    const QString restore = state->restore;
    activeContextTabs.erase(state);

    int selected = -1;
    {
        Base::StateLocker lock(updating);

        const int index = indexOfTab(definition);
        if (index >= 0) {
            ribbonBar->removeTab(index);
            visibleTabs.erase(visibleTabs.begin() + index);
            if (index < static_cast<int>(pageBuilt.size())) {
                pageBuilt.erase(pageBuilt.begin() + index);
            }
        }

        ribbonBar->setContextTabPresent(!activeContextTabs.empty());

        selected = indexOfTab(restore);
        if (selected < 0) {
            selected = ribbonBar->currentIndex();
        }

        ribbonBar->setCurrentIndex(selected);
    }

    buildPage(selected);
}

const RibbonManager::TabDefinition* RibbonManager::findContextTab(const QString& id) const
{
    if (id.isEmpty()) {
        return nullptr;
    }

    for (const TabDefinition& tab : contextTabs) {
        if (tab.id == id) {
            return &tab;
        }
    }

    return nullptr;
}

int RibbonManager::indexOfTab(const TabDefinition* tab) const
{
    for (std::size_t i = 0; i < visibleTabs.size(); ++i) {
        if (visibleTabs[i] == tab) {
            return static_cast<int>(i);
        }
    }

    return -1;
}

int RibbonManager::indexOfTab(const QString& id) const
{
    if (id.isEmpty()) {
        return -1;
    }

    for (std::size_t i = 0; i < visibleTabs.size(); ++i) {
        if (visibleTabs[i]->id == id) {
            return static_cast<int>(i);
        }
    }

    return -1;
}

void RibbonManager::onWorkbenchActivated(const QString& workbench)
{
    if (updating || ribbonBar.isNull()) {
        return;
    }

    rebuildTabs(workbench);
}

void RibbonManager::onTabActivated(int index)
{
    if (updating || ribbonBar.isNull()) {
        return;
    }

    if (index < 0 || index >= static_cast<int>(visibleTabs.size())) {
        return;
    }

    const TabDefinition* tab = visibleTabs[index];
    if (!tab->context && !tab->workbench.isEmpty()
        && tab->workbench.toStdString() != WorkbenchManager::instance()->activeName()) {
        // The workbench has to come up first: it is what registers the commands
        // the page is about to resolve.
        Base::StateLocker lock(updating);
        Application::Instance->activateWorkbench(tab->workbench.toLatin1().constData());
    }

    buildPage(index);
}

void RibbonManager::loadWorkspace()
{
    if (workspaceLoaded) {
        return;
    }

    workspaceLoaded = true;

    QFile file(QString::fromLatin1(workspaceResource));
    if (!file.open(QIODevice::ReadOnly)) {
        Base::Console().error("Ribbon: cannot open the workspace definition '%s'\n", workspaceResource);
        return;
    }

    QJsonParseError error {};
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &error);
    file.close();

    if (error.error != QJsonParseError::NoError) {
        Base::Console().error(
            "Ribbon: the workspace definition is not valid JSON: %s\n",
            error.errorString().toUtf8().constData()
        );
        return;
    }

    if (!document.isObject()) {
        Base::Console().error("Ribbon: the workspace definition is not a JSON object\n");
        return;
    }

    const QJsonObject root = document.object();

    const QJsonArray tabs = root.value(QLatin1String("tabs")).toArray();
    for (int i = 0; i < tabs.size(); ++i) {
        const QJsonValue value = tabs.at(i);
        if (!value.isObject()) {
            continue;
        }

        TabDefinition tab;
        if (parseTab(value.toObject(), tab)) {
            workspaceTabs.push_back(std::move(tab));
        }
    }

    const QJsonArray contexts = root.value(QLatin1String("contextTabs")).toArray();
    for (int i = 0; i < contexts.size(); ++i) {
        const QJsonValue value = contexts.at(i);
        if (!value.isObject()) {
            continue;
        }

        TabDefinition tab;
        if (parseTab(value.toObject(), tab)) {
            tab.context = true;
            contextTabs.push_back(std::move(tab));
        }
    }
}

bool RibbonManager::parseTab(const QJsonObject& source, TabDefinition& tab)
{
    tab.id = source.value(QLatin1String("id")).toString();
    if (tab.id.isEmpty()) {
        Base::Console().warning("Ribbon: skipping a tab without an id\n");
        return false;
    }

    tab.workbench = source.value(QLatin1String("workbench")).toString();
    tab.optional = source.value(QLatin1String("optional")).toBool(false);

    const QJsonArray panels = source.value(QLatin1String("panels")).toArray();
    for (int i = 0; i < panels.size(); ++i) {
        const QJsonValue value = panels.at(i);
        if (!value.isObject()) {
            continue;
        }

        PanelDefinition panel;
        if (parsePanel(value.toObject(), panel)) {
            tab.panels.push_back(std::move(panel));
        }
    }

    return true;
}

bool RibbonManager::parsePanel(const QJsonObject& source, PanelDefinition& panel)
{
    panel.caption = source.value(QLatin1String("caption")).toString();
    panel.alignRight = source.value(QLatin1String("align")).toString() == QLatin1String("right");
    panel.initWorkbench = source.value(QLatin1String("initWorkbench")).toString();

    if (!panel.initWorkbench.isEmpty()) {
        Application::Instance->ensureWorkbenchInitialized(
            panel.initWorkbench.toUtf8().constData()
        );
    }

    const QJsonArray items = source.value(QLatin1String("items")).toArray();
    for (int i = 0; i < items.size(); ++i) {
        const QJsonValue value = items.at(i);
        if (!value.isObject()) {
            continue;
        }

        ItemDefinition item;
        if (parseItem(value.toObject(), item) && !item.command.isEmpty()) {
            panel.items.push_back(std::move(item));
        }
    }

    const QJsonArray menuItems = source.value(QLatin1String("menu")).toArray();
    for (int i = 0; i < menuItems.size(); ++i) {
        const QJsonValue value = menuItems.at(i);
        if (!value.isObject()) {
            continue;
        }

        ItemDefinition item;
        if (parseItem(value.toObject(), item)) {
            panel.menuItems.push_back(std::move(item));
        }
    }

    return !panel.items.empty() || !panel.menuItems.empty();
}

bool RibbonManager::parseItem(const QJsonObject& source, ItemDefinition& item)
{
    item.command = source.value(QLatin1String("command")).toString();
    item.label = source.value(QLatin1String("label")).toString();
    item.primary = source.value(QLatin1String("primary")).toBool(false);
    item.optional = source.value(QLatin1String("optional")).toBool(false);

    const QJsonArray subCommands = source.value(QLatin1String("commands")).toArray();
    for (int i = 0; i < subCommands.size(); ++i) {
        const QString subCommand = subCommands.at(i).toString();
        if (!subCommand.isEmpty()) {
            item.subCommands.append(subCommand);
        }
    }

    // A menu entry may be a bare submenu, which needs a name and something to
    // put under it but no command of its own.
    return !item.command.isEmpty() || (!item.label.isEmpty() && !item.subCommands.isEmpty());
}

void RibbonManager::rebuildTabs(const QString& workbench)
{
    if (ribbonBar.isNull()) {
        return;
    }

    loadWorkspace();

    QStringList available;
    {
        Base::PyGILStateLocker lock;
        available = Application::Instance->workbenches();
    }

    int selected = -1;
    {
        Base::StateLocker lock(updating);

        ribbonBar->clear();
        visibleTabs.clear();
        pageBuilt.clear();

        for (const TabDefinition& tab : workspaceTabs) {
            const bool missing = !tab.workbench.isEmpty() && !available.contains(tab.workbench);
            if (tab.optional && missing) {
                Base::Console().log(
                    "Ribbon: dropping optional tab '%s', workbench '%s' is not available\n",
                    tab.id.toUtf8().constData(),
                    tab.workbench.toUtf8().constData()
                );
                continue;
            }

            visibleTabs.push_back(&tab);
        }

        bool described = false;
        for (const TabDefinition* tab : visibleTabs) {
            if (tab->workbench == workbench) {
                described = true;
                break;
            }
        }

        // A workbench that a context tab speaks for is described even while that tab is
        // not pushed yet. Sketcher activates before enterEditMode() pushes SKETCH, so
        // testing only the pushed tabs would generate a redundant "Sketcher" tab that
        // then sits next to the contextual one.
        for (const TabDefinition& tab : contextTabs) {
            if (!tab.workbench.isEmpty() && tab.workbench == workbench) {
                described = true;
                break;
            }
        }

        if (!described && !workbench.isEmpty()) {
            generatedTab.id = Application::Instance->workbenchMenuText(workbench);
            if (generatedTab.id.isEmpty()) {
                generatedTab.id = workbench;
            }
            generatedTab.workbench = workbench;
            generatedTab.optional = false;
            generatedTab.generated = true;

            const auto remembered = rememberedToolBars.find(workbench);
            generatedTab.panels = remembered != rememberedToolBars.end()
                ? remembered->second
                : std::vector<PanelDefinition> {};

            visibleTabs.push_back(&generatedTab);
        }

        for (std::size_t i = 0; i < visibleTabs.size(); ++i) {
            if (selected < 0 && visibleTabs[i]->workbench == workbench) {
                selected = static_cast<int>(i);
            }
        }

        // Context tabs trail the strip, and a mode that is still running keeps
        // the tab it pushed rather than losing it to the workbench switch.
        for (const ContextTabState& state : activeContextTabs) {
            visibleTabs.push_back(state.tab);
        }

        for (const TabDefinition* tab : visibleTabs) {
            // The id stays the untranslated lookup key; only the strip is named
            // in the user's language.
            ribbonBar->addTab(translateRibbon(tab->id));
        }

        ribbonBar->setContextTabPresent(!activeContextTabs.empty());

        pageBuilt.assign(visibleTabs.size(), false);

        if (visibleTabs.empty()) {
            return;
        }

        if (!activeContextTabs.empty()) {
            selected = static_cast<int>(visibleTabs.size()) - 1;
        }
        else if (selected < 0) {
            selected = 0;
        }

        ribbonBar->setCurrentIndex(selected);
    }

    buildPage(selected);
}

void RibbonManager::retranslate()
{
    if (ribbonBar.isNull()) {
        return;
    }

    // Every caption is read from the definition while a page is built, so the
    // strip has to be built again for a language change to reach it. The pushed
    // context tabs are kept, and the tab that matches the active workbench is
    // selected again.
    const std::string active = WorkbenchManager::instance()->activeName();
    if (!active.empty()) {
        rebuildTabs(QString::fromStdString(active));
    }
}

void RibbonManager::buildPage(int index)
{
    if (ribbonBar.isNull()) {
        return;
    }

    if (index < 0 || index >= static_cast<int>(visibleTabs.size())) {
        return;
    }

    if (index < static_cast<int>(pageBuilt.size()) && pageBuilt[index]) {
        return;
    }

    ribbonBar->setPage(index, createPage(*visibleTabs[index]));

    if (index < static_cast<int>(pageBuilt.size())) {
        pageBuilt[index] = true;
    }
}

QWidget* RibbonManager::createPage(const TabDefinition& tab)
{
    auto* page = new RibbonPage();
    const QString tabKey = tab.key();

    for (const PanelDefinition& panelDefinition : tab.panels) {
        const QString panelKey = tabKey + keySeparator + panelDefinition.caption;
        const QString caption = panelDefinition.displayCaption.isEmpty()
            ? translateRibbon(panelDefinition.caption)
            : panelDefinition.displayCaption;
        auto* panel = new RibbonPanel(panelKey, caption, page);

        // The row is the definition's unless the user has arranged one.
        QStringList storedRow;
        const bool customised = rowOverride(tabKey, panelDefinition.caption, storedRow);
        const std::vector<ItemDefinition> rowItems =
            customised ? resolveRow(panelDefinition, storedRow) : panelDefinition.items;

        for (const ItemDefinition& item : rowItems) {
            auto* button = new RibbonButton(panel);
            const bool bound = button->setCommand(
                item.command,
                translateRibbon(item.label),
                item.subCommands,
                ButtonSize::Large,
                item.optional
            );
            if (!bound) {
                delete button;
                continue;
            }

            button->setPrimary(item.primary);
            panel->addButton(button);
        }
        panel->setCustomised(customised);

        // A definition entry the user took out of the row stays reachable
        // through the drop-down, ahead of the curated list when that does not
        // already carry it.
        std::vector<ItemDefinition> parked;
        if (customised) {
            for (const ItemDefinition& item : panelDefinition.items) {
                if (!storedRow.contains(item.command) && !menuCovers(panelDefinition, item.command)) {
                    parked.push_back(item);
                }
            }
        }

        RibbonPanelMenu* menu = panel->dropDown();
        fillPanelMenu(menu, parked);
        if (!menu->isEmpty() && !panelDefinition.menuItems.empty()) {
            menu->addSeparator();
        }
        fillPanelMenu(menu, panelDefinition.menuItems);

        if (panel->isEmpty()) {
            delete panel;
            continue;
        }

        // The definitions outlive the page: the tab lives in workspaceTabs,
        // contextTabs or generatedTab, none of which is reshaped once loaded.
        const TabDefinition* tabDefinition = &tab;
        const QString captionKey = panelDefinition.caption;
        QStringList definedRow;
        for (const ItemDefinition& item : panelDefinition.items) {
            definedRow.append(item.command);
        }
        connect(
            panel,
            &RibbonPanel::rowChanged,
            this,
            [this, tabDefinition, captionKey, definedRow](const QStringList& commands) {
                // A row put back the way the definition has it is not an
                // arrangement to keep, and the panel is no longer customised.
                if (commands == definedRow) {
                    clearRowOverride(tabDefinition->key(), captionKey);
                }
                else {
                    storeRowOverride(tabDefinition->key(), captionKey, commands);
                }
                schedulePageRebuild(tabDefinition);
            }
        );
        connect(panel, &RibbonPanel::resetRequested, this, [this, tabDefinition, captionKey]() {
            clearRowOverride(tabDefinition->key(), captionKey);
            schedulePageRebuild(tabDefinition);
        });
        connect(panel, &RibbonPanel::resetAllRequested, this, &RibbonManager::resetPanelArrangements);

        page->addPanel(panel, panelDefinition.alignRight);
    }

    return page;
}

void RibbonManager::schedulePageRebuild(const TabDefinition* tab)
{
    // Queued: the panel that asked is still inside the event that made it ask,
    // and setPage() deletes the page it belongs to.
    QTimer::singleShot(0, this, [this, tab]() {
        const int index = indexOfTab(tab);
        if (index < 0) {
            return;
        }
        if (index < static_cast<int>(pageBuilt.size())) {
            pageBuilt[index] = false;
        }
        buildPage(index);
    });
}

void RibbonManager::scheduleAllPagesRebuild()
{
    QTimer::singleShot(0, this, [this]() {
        if (ribbonBar.isNull()) {
            return;
        }
        // The others are rebuilt when their tab is next selected.
        pageBuilt.assign(pageBuilt.size(), false);
        buildPage(ribbonBar->currentIndex());
    });
}

bool RibbonManager::rowOverride(const QString& tabKey, const QString& caption, QStringList& row)
{
    // Looked up rather than fetched by path, so that a user who never arranged
    // a panel does not get the groups written into user.cfg on every page.
    ParameterGrp::handle preferences = App::GetApplication().GetParameterGroupByPath(preferencesPath);
    if (!preferences->HasGroup(ribbonGroupName)) {
        return false;
    }
    ParameterGrp::handle ribbon = preferences->GetGroup(ribbonGroupName);
    if (!ribbon->HasGroup(panelsGroupName)) {
        return false;
    }

    ParameterGrp::handle panels = ribbon->GetGroup(panelsGroupName);
    const QByteArray tabName = parameterName(tabKey);
    if (!panels->HasGroup(tabName.constData())) {
        return false;
    }

    ParameterGrp::handle tabGroup = panels->GetGroup(tabName.constData());
    const QByteArray panelName = parameterName(caption);
    if (!tabGroup->HasGroup(panelName.constData())) {
        return false;
    }

    const std::string stored = tabGroup->GetGroup(panelName.constData())->GetASCII(rowKey);
    row = QString::fromStdString(stored).split(rowSeparator, Qt::SkipEmptyParts);
    return true;
}

void RibbonManager::storeRowOverride(const QString& tabKey, const QString& caption, const QStringList& row)
{
    App::GetApplication()
        .GetParameterGroupByPath(panelLayoutPreferences)
        ->GetGroup(parameterName(tabKey).constData())
        ->GetGroup(parameterName(caption).constData())
        ->SetASCII(rowKey, row.join(rowSeparator).toUtf8().constData());
}

void RibbonManager::clearRowOverride(const QString& tabKey, const QString& caption)
{
    ParameterGrp::handle panels = App::GetApplication().GetParameterGroupByPath(panelLayoutPreferences);
    const QByteArray tabName = parameterName(tabKey);
    if (!panels->HasGroup(tabName.constData())) {
        return;
    }

    bool tabEmpty = false;
    {
        // A group still referenced from here would only be cleared, not
        // removed, by the parent's RemoveGrp() below.
        ParameterGrp::handle tabGroup = panels->GetGroup(tabName.constData());
        tabGroup->RemoveGrp(parameterName(caption).constData());
        tabEmpty = tabGroup->GetGroups().empty();
    }
    if (tabEmpty) {
        panels->RemoveGrp(tabName.constData());
    }
}

void RibbonManager::clearAllRowOverrides()
{
    App::GetApplication().GetParameterGroupByPath(panelLayoutPreferences)->Clear();
}

std::vector<RibbonManager::ItemDefinition> RibbonManager::resolveRow(
    const PanelDefinition& panel,
    const QStringList& commands
)
{
    std::vector<ItemDefinition> items;
    for (const QString& command : commands) {
        // The definition knows how the command is labelled and what it splits
        // into; a command it only lists inside a submenu becomes a plain button.
        auto matches = [&command](const ItemDefinition& item) {
            return item.command == command;
        };
        auto found = std::find_if(panel.items.begin(), panel.items.end(), matches);
        if (found == panel.items.end()) {
            found = std::find_if(panel.menuItems.begin(), panel.menuItems.end(), matches);
            if (found == panel.menuItems.end()) {
                ItemDefinition plain;
                plain.command = command;
                // A stored command that has since gone (an add-on removed, a
                // command renamed) is not a mistake in the definition, so it
                // is dropped from the row without a warning on every page.
                plain.optional = true;
                items.push_back(std::move(plain));
                continue;
            }
        }
        items.push_back(*found);
    }
    return items;
}

bool RibbonManager::menuCovers(const PanelDefinition& panel, const QString& command)
{
    for (const ItemDefinition& item : panel.menuItems) {
        if (item.command == command || item.subCommands.contains(command)) {
            return true;
        }
    }
    return false;
}

void RibbonManager::fillPanelMenu(RibbonPanelMenu* menu, const std::vector<ItemDefinition>& items)
{
    for (const ItemDefinition& item : items) {
        Gui::Action* guiAction = resolveGuiAction(item.command);
        QAction* action = guiAction ? guiAction->action() : nullptr;

        if (!item.command.isEmpty() && !action) {
            reportMissing(item.command, item.optional);
            continue;
        }

        QList<QAction*> children;
        for (const QString& subCommand : item.subCommands) {
            if (QAction* child = RibbonButton::resolveAction(subCommand)) {
                RibbonPanelMenu::tagCommand(child, subCommand);
                children.append(child);
            }
            else {
                reportMissing(subCommand, item.optional);
            }
        }

        // A group command already carries its variants, which is how a single
        // FreeCAD command stands in for a row of Fusion entries. Those variants
        // are not commands of their own, so they are not named for dragging.
        Gui::ActionGroup* group = nullptr;
        if (children.isEmpty()) {
            group = qobject_cast<Gui::ActionGroup*>(guiAction);
            if (group) {
                children = group->actions();
            }
        }

        if (!children.isEmpty()) {
            const QString title =
                item.label.isEmpty() && action ? action->text() : translateRibbon(item.label);
            if (title.isEmpty()) {
                continue;
            }

            RibbonPanelMenu* submenu = menu->addSubmenu(title);
            if (action) {
                submenu->setIcon(action->icon());
                RibbonPanelMenu::tagCommand(submenu->menuAction(), item.command);
            }
            submenu->addActions(children);
            RibbonButton::followGroupMenu(group, submenu);
            continue;
        }

        if (!action) {
            continue;
        }

        QAction* entry = item.label.isEmpty()
            ? action
            : RibbonPanelMenu::createProxyAction(action, translateRibbon(item.label), menu);
        RibbonPanelMenu::tagCommand(entry, item.command);
        menu->addAction(entry);
    }
}

#include "moc_RibbonManager.cpp"
