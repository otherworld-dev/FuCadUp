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


#include <QAbstractItemView>
#include <QFont>
#include <QFrame>
#include <QHBoxLayout>
#include <QSignalBlocker>
#include <QSize>
#include <QSizePolicy>
#include <QStackedWidget>
#include <QStyle>
#include <QTabBar>
#include <QVBoxLayout>

#include <Base/Console.h>
#include <Gui/Action.h>
#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/WorkbenchSelector.h>

#include "RibbonBar.h"


using namespace Gui;
using namespace Gui::Ribbon;

namespace
{
// Matches Fusion: a tab strip over a page tall enough for a row of icon-only
// buttons, plus the panel caption underneath it.
constexpr int ribbonBarHeight = 86;
// Selected on by the stylesheet as QTabBar#RibbonTabBar[contextTab="true"].
constexpr const char* contextTabProperty = "contextTab";
// The workspace block keeps the side margin of a panel body so that the
// selector lines up with the buttons beside it.
constexpr int workspaceBlockSideMargin = 8;
constexpr int workspaceBlockVerticalMargin = 6;
constexpr int workspaceSelectorMinimumWidth = 180;
constexpr int workspaceSelectorIconExtent = 20;
// The selector names the workspace, so it reads a step larger than the
// captions under the panels.
constexpr int workspaceSelectorPointSizeDelta = 2;
constexpr int separatorWidth = 1;
}  // namespace


RibbonBar::RibbonBar(QWidget* parent)
    : QWidget(parent)
    , tabBar(nullptr)
    , pageStack(nullptr)
{
    setObjectName(QStringLiteral("RibbonBar"));
    setAttribute(Qt::WA_StyledBackground, true);
    setFixedHeight(ribbonBarHeight);
    setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);

    auto* layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    tabBar = new QTabBar(this);
    tabBar->setObjectName(QStringLiteral("RibbonTabBar"));
    tabBar->setExpanding(false);
    tabBar->setDrawBase(false);
    tabBar->setUsesScrollButtons(true);
    tabBar->setElideMode(Qt::ElideNone);
    tabBar->setFocusPolicy(Qt::NoFocus);
    tabBar->setProperty(contextTabProperty, false);

    auto* pageRow = new QWidget(this);
    pageRow->setObjectName(QStringLiteral("RibbonPageRow"));
    pageRow->setAttribute(Qt::WA_StyledBackground, true);

    auto* rowLayout = new QHBoxLayout(pageRow);
    rowLayout->setContentsMargins(0, 0, 0, 0);
    rowLayout->setSpacing(0);

    pageStack = new QStackedWidget(pageRow);
    pageStack->setObjectName(QStringLiteral("RibbonPages"));
    pageStack->setFrameShape(QFrame::NoFrame);

    if (QWidget* workspaceBlock = createWorkspaceBlock(pageRow)) {
        rowLayout->addWidget(workspaceBlock, 0);
    }
    rowLayout->addWidget(pageStack, 1);

    layout->addWidget(tabBar, 0);
    layout->addWidget(pageRow, 1);

    connect(tabBar, &QTabBar::currentChanged, this, [this](int index) {
        if (index >= 0 && index < pageStack->count()) {
            pageStack->setCurrentIndex(index);
        }
        Q_EMIT tabActivated(index);
    });
}

QWidget* RibbonBar::createWorkspaceBlock(QWidget* parent)
{
    if (!Application::Instance) {
        return nullptr;
    }

    CommandManager& manager = Application::Instance->commandManager();
    Command* command = manager.getCommandByName("Std_Workbench");
    if (!command) {
        Base::Console().warning(
            "Ribbon: 'Std_Workbench' is not registered, the workspace selector is unavailable\n"
        );
        return nullptr;
    }

    command->initAction();
    auto* group = qobject_cast<WorkbenchGroup*>(command->getAction());
    if (!group) {
        Base::Console().warning("Ribbon: 'Std_Workbench' provides no workbench group\n");
        return nullptr;
    }

    auto* block = new QWidget(parent);
    block->setObjectName(QStringLiteral("RibbonWorkspaceBlock"));
    block->setAttribute(Qt::WA_StyledBackground, true);

    auto* blockLayout = new QHBoxLayout(block);
    blockLayout->setContentsMargins(0, 0, 0, 0);
    blockLayout->setSpacing(0);

    auto* selector = new WorkbenchComboBox(group, block);
    selector->setObjectName(QStringLiteral("RibbonWorkspaceSelector"));
    selector->setIconSize(QSize(workspaceSelectorIconExtent, workspaceSelectorIconExtent));
    selector->setMinimumWidth(workspaceSelectorMinimumWidth);
    // Sized for the longest workspace name, so the block never shifts the
    // panels when the selection changes.
    selector->setSizeAdjustPolicy(QComboBox::AdjustToContents);
    selector->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Expanding);

    QFont selectorFont = selector->font();
    if (selectorFont.pointSizeF() > 0.0) {
        // The popup list keeps the regular size; only the box grows.
        selector->view()->setFont(selectorFont);
        selectorFont.setPointSizeF(selectorFont.pointSizeF() + workspaceSelectorPointSizeDelta);
        selector->setFont(selectorFont);
    }

    auto* selectorLayout = new QHBoxLayout();
    selectorLayout->setContentsMargins(
        workspaceBlockSideMargin,
        workspaceBlockVerticalMargin,
        workspaceBlockSideMargin,
        workspaceBlockVerticalMargin
    );
    selectorLayout->setSpacing(0);
    selectorLayout->addWidget(selector);

    // The same rule a panel draws down its right edge, so the block reads as
    // the first panel of every page.
    auto* separator = new QWidget(block);
    separator->setObjectName(QStringLiteral("RibbonPanelSeparator"));
    separator->setAttribute(Qt::WA_StyledBackground, true);
    separator->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Expanding);
    separator->setFixedWidth(separatorWidth);

    blockLayout->addLayout(selectorLayout);
    blockLayout->addWidget(separator);

    return block;
}

void RibbonBar::clear()
{
    const QSignalBlocker blocker(tabBar);

    while (tabBar->count() > 0) {
        tabBar->removeTab(0);
    }

    while (pageStack->count() > 0) {
        QWidget* page = pageStack->widget(0);
        pageStack->removeWidget(page);
        delete page;
    }
}

int RibbonBar::addTab(const QString& title)
{
    const QSignalBlocker blocker(tabBar);

    const int index = tabBar->addTab(title);
    pageStack->insertWidget(index, new QWidget(pageStack));
    return index;
}

void RibbonBar::removeTab(int index)
{
    if (index < 0 || index >= tabBar->count()) {
        return;
    }

    const QSignalBlocker blocker(tabBar);

    tabBar->removeTab(index);

    if (index < pageStack->count()) {
        QWidget* page = pageStack->widget(index);
        pageStack->removeWidget(page);
        delete page;
    }
}

int RibbonBar::count() const
{
    return tabBar->count();
}

void RibbonBar::setContextTabPresent(bool present)
{
    if (tabBar->property(contextTabProperty).toBool() == present) {
        return;
    }

    tabBar->setProperty(contextTabProperty, present);

    // A rule that selects on a dynamic property is only re-evaluated once the
    // style is asked to look at the widget again.
    tabBar->style()->unpolish(tabBar);
    tabBar->style()->polish(tabBar);
    tabBar->update();
}

QString RibbonBar::tabText(int index) const
{
    return tabBar->tabText(index);
}

void RibbonBar::setPage(int index, QWidget* page)
{
    if (!page) {
        return;
    }

    if (index < 0 || index >= pageStack->count()) {
        delete page;
        return;
    }

    QWidget* previous = pageStack->widget(index);
    const bool wasCurrent = pageStack->currentIndex() == index;

    pageStack->insertWidget(index, page);
    pageStack->removeWidget(previous);
    delete previous;

    if (wasCurrent) {
        pageStack->setCurrentIndex(index);
    }
}

int RibbonBar::currentIndex() const
{
    return tabBar->currentIndex();
}

void RibbonBar::setCurrentIndex(int index)
{
    if (index < 0 || index >= tabBar->count()) {
        return;
    }

    tabBar->setCurrentIndex(index);
    pageStack->setCurrentIndex(index);
}

#include "moc_RibbonBar.cpp"
