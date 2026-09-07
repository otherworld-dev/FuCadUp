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

#include <QAction>
#include <QFont>
#include <QMenu>
#include <QPair>
#include <QSizePolicy>
#include <QToolButton>

#include "RibbonPage.h"
#include "RibbonPageLayout.h"
#include "RibbonPanel.h"
#include "RibbonPanelMenu.h"


using namespace Gui::Ribbon;

namespace
{
constexpr int overflowButtonWidth = 24;
constexpr int overflowGlyphPointSizeDelta = 3;
}  // namespace


RibbonPage::RibbonPage(QWidget* parent)
    : QWidget(parent)
    , pageLayout(nullptr)
    , overflowButton(nullptr)
    , overflowMenu(nullptr)
{
    setObjectName(QStringLiteral("RibbonPage"));
    // A plain QWidget only honours a stylesheet background with this attribute.
    setAttribute(Qt::WA_StyledBackground, true);

    overflowMenu = new QMenu(this);
    overflowMenu->setObjectName(QStringLiteral("RibbonPageOverflowMenu"));
    connect(overflowMenu, &QMenu::aboutToShow, this, &RibbonPage::fillOverflowMenu);

    overflowButton = new QToolButton(this);
    overflowButton->setObjectName(QStringLiteral("RibbonPageOverflowButton"));
    overflowButton->setText(QStringLiteral("»"));
    overflowButton->setToolTip(tr("More panels"));
    overflowButton->setToolButtonStyle(Qt::ToolButtonTextOnly);
    overflowButton->setPopupMode(QToolButton::InstantPopup);
    overflowButton->setAutoRaise(true);
    // Walked with the arrow keys like the buttons of a panel; see RibbonBar.
    overflowButton->setFocusPolicy(Qt::NoFocus);
    // The glyph is the whole button, so it reads a step larger than a caption.
    QFont glyphFont = overflowButton->font();
    if (glyphFont.pointSizeF() > 0.0) {
        glyphFont.setPointSizeF(glyphFont.pointSizeF() + overflowGlyphPointSizeDelta);
        overflowButton->setFont(glyphFont);
    }
    overflowButton->setFixedWidth(overflowButtonWidth);
    overflowButton->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Expanding);
    overflowButton->setMenu(overflowMenu);
    overflowButton->hide();

    pageLayout = new RibbonPageLayout(this, overflowButton);
    pageLayout->setContentsMargins(2, 1, 2, 0);
}

void RibbonPage::addPanel(RibbonPanel* panel, bool trailing)
{
    pageLayout->addPanel(panel, trailing);
}

QList<QToolButton*> RibbonPage::keyboardButtons() const
{
    // Panels and the overflow button in the order they sit on the page, and
    // inside a panel its buttons before its caption: the order the eye reads
    // them in. A panel knows which of its buttons it has folded away, and a
    // panel that left the page has nothing to offer the keyboard.
    QList<QPair<int, QList<QToolButton*>>> groups;
    for (RibbonPanel* panel : findChildren<RibbonPanel*>(QString(), Qt::FindDirectChildrenOnly)) {
        if (panel->isVisibleTo(this)) {
            groups.append({panel->x(), panel->keyboardButtons()});
        }
    }
    if (overflowButton->isVisibleTo(this)) {
        groups.append({overflowButton->x(), {overflowButton}});
    }
    std::stable_sort(groups.begin(), groups.end(), [](const auto& a, const auto& b) {
        return a.first < b.first;
    });

    QList<QToolButton*> buttons;
    for (const auto& group : groups) {
        buttons.append(group.second);
    }
    return buttons;
}

void RibbonPage::setCollapsedPanels(const QList<RibbonPanel*>& panels)
{
    collapsed.clear();
    for (RibbonPanel* panel : panels) {
        collapsed.append(panel);
    }
}

void RibbonPage::fillOverflowMenu()
{
    // The entries are the panels' own drop-downs, which stay owned by their
    // panels: clear() only takes them out again.
    overflowMenu->clear();
    for (const QPointer<RibbonPanel>& panel : collapsed) {
        if (panel) {
            overflowMenu->addMenu(panel->dropDown());
        }
    }
}

#include "moc_RibbonPage.cpp"
