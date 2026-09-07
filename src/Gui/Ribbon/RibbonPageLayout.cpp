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

#include <QLayoutItem>
#include <QVector>
#include <QWidget>
#include <QWidgetItem>

#include "RibbonPage.h"
#include "RibbonPageLayout.h"
#include "RibbonPanel.h"


using namespace Gui::Ribbon;


RibbonPageLayout::RibbonPageLayout(RibbonPage* page, QWidget* overflowButton)
    : QLayout(page)
    , page(page)
    , overflowButton(overflowButton)
{
    setSpacing(0);
}

RibbonPageLayout::~RibbonPageLayout()
{
    while (QLayoutItem* item = takeAt(0)) {
        delete item;
    }
}

void RibbonPageLayout::addPanel(RibbonPanel* panel, bool trailing)
{
    if (!panel) {
        return;
    }

    addChildWidget(panel);
    entries.append({new QWidgetItem(panel), panel, trailing});
    invalidate();
}

void RibbonPageLayout::addItem(QLayoutItem* item)
{
    // Only addPanel() knows which group a panel belongs to; anything that
    // arrives through the generic route is treated as leading.
    auto* panel = qobject_cast<RibbonPanel*>(item->widget());
    entries.append({item, panel, false});
    invalidate();
}

int RibbonPageLayout::count() const
{
    return static_cast<int>(entries.size());
}

QLayoutItem* RibbonPageLayout::itemAt(int index) const
{
    return index >= 0 && index < entries.size() ? entries.at(index).item : nullptr;
}

QLayoutItem* RibbonPageLayout::takeAt(int index)
{
    if (index < 0 || index >= entries.size()) {
        return nullptr;
    }

    QLayoutItem* item = entries.at(index).item;
    collapsed.removeAll(entries.at(index).panel);
    entries.removeAt(index);
    invalidate();
    return item;
}

Qt::Orientations RibbonPageLayout::expandingDirections() const
{
    return Qt::Horizontal;
}

QSize RibbonPageLayout::sizeHint() const
{
    // Asked of the panels themselves rather than of the items, which report
    // nothing for a panel that has left the page and would let the page ask
    // for less than it takes to bring that panel back.
    const QMargins margins = contentsMargins();
    int width = 0;
    int height = 0;
    for (const Entry& entry : entries) {
        const QSize hint = entry.panel ? entry.panel->sizeHint() : entry.item->sizeHint();
        width += hint.width();
        height = std::max(height, hint.height());
    }

    return QSize(width + margins.left() + margins.right(), height + margins.top() + margins.bottom());
}

QSize RibbonPageLayout::minimumSize() const
{
    const QMargins margins = contentsMargins();
    int height = 0;
    for (const Entry& entry : entries) {
        const QSize minimum = entry.panel ? entry.panel->minimumSizeHint()
                                          : entry.item->minimumSize();
        height = std::max(height, minimum.height());
    }

    return QSize(
        overflowButton->sizeHint().width() + margins.left() + margins.right(),
        height + margins.top() + margins.bottom()
    );
}

void RibbonPageLayout::setGeometry(const QRect& rect)
{
    QLayout::setGeometry(rect);

    const QRect area = contentsRect();
    const qsizetype n = entries.size();
    if (n == 0) {
        overflowButton->hide();
        return;
    }

    QVector<int> minimums;
    QVector<int> widths;
    minimums.reserve(n);
    widths.reserve(n);
    int needed = 0;
    for (const Entry& entry : entries) {
        const QWidget* panel = entry.panel ? entry.panel : entry.item->widget();
        const int minimum = panel ? panel->minimumSizeHint().width()
                                  : entry.item->minimumSize().width();
        const int hint = panel ? panel->sizeHint().width() : entry.item->sizeHint().width();
        minimums.append(minimum);
        widths.append(std::max(hint, minimum));
        needed += minimum;
    }

    // Narrower than the captions alone need, whole panels leave the page, from
    // the right and leading panels first, for the overflow button that then
    // takes their place. The tools a workspace leads with go last.
    QVector<bool> shown(n, true);
    int reserved = 0;
    if (needed > area.width()) {
        reserved = overflowButton->sizeHint().width();
        for (int pass = 0; pass < 2 && needed + reserved > area.width(); ++pass) {
            const bool trailing = pass == 1;
            for (qsizetype i = n - 1; i >= 0 && needed + reserved > area.width(); --i) {
                if (entries.at(i).trailing != trailing) {
                    continue;
                }
                shown[i] = false;
                needed -= minimums[i];
            }
        }
    }

    // Shrink from the right: leading panels last to first, then trailing panels
    // last to first, each down to its minimum before the next one is touched.
    int deficit = reserved - area.width();
    for (qsizetype i = 0; i < n; ++i) {
        if (shown[i]) {
            deficit += widths[i];
        }
    }
    for (int pass = 0; pass < 2 && deficit > 0; ++pass) {
        const bool trailing = pass == 1;
        for (qsizetype i = n - 1; i >= 0 && deficit > 0; --i) {
            if (entries.at(i).trailing != trailing || !shown[i]) {
                continue;
            }
            const int give = std::min(deficit, std::max(0, widths[i] - minimums[i]));
            widths[i] -= give;
            deficit -= give;
        }
    }

    // The panels that leave fold everything into their drop-down, which is
    // what the overflow button lists for them.
    QList<RibbonPanel*> leaving;
    for (qsizetype i = 0; i < n; ++i) {
        if (RibbonPanel* panel = entries.at(i).panel) {
            panel->setCollapsed(!shown[i]);
            if (!shown[i]) {
                leaving.append(panel);
            }
        }
    }

    int trailingWidth = 0;
    RibbonPanel* lastLeading = nullptr;
    RibbonPanel* lastTrailing = nullptr;
    for (qsizetype i = 0; i < n; ++i) {
        if (!shown[i]) {
            continue;
        }
        if (entries.at(i).trailing) {
            trailingWidth += widths[i];
            lastTrailing = entries.at(i).panel;
        }
        else {
            lastLeading = entries.at(i).panel;
        }
    }

    int leadingX = area.left();
    for (qsizetype i = 0; i < n; ++i) {
        const Entry& entry = entries.at(i);
        if (entry.trailing) {
            continue;
        }
        QWidget* widget = entry.item->widget();
        if (!shown[i]) {
            if (widget) {
                widget->hide();
            }
            continue;
        }
        // Shown first: the item sets no geometry on a hidden widget.
        if (widget) {
            widget->show();
        }
        entry.item->setGeometry(QRect(leadingX, area.top(), widths[i], area.height()));
        leadingX += widths[i];
    }

    if (reserved > 0) {
        overflowButton->setGeometry(QRect(leadingX, area.top(), reserved, area.height()));
        overflowButton->show();
        leadingX += reserved;
    }
    else {
        overflowButton->hide();
    }

    // Trailing panels sit against the right edge, or straight after the
    // leading ones when the page is narrower than even the minimums.
    int trailingX = std::max(area.right() + 1 - trailingWidth, leadingX);
    for (qsizetype i = 0; i < n; ++i) {
        const Entry& entry = entries.at(i);
        if (!entry.trailing) {
            continue;
        }
        QWidget* widget = entry.item->widget();
        if (!shown[i]) {
            if (widget) {
                widget->hide();
            }
            continue;
        }
        // Shown first: the item sets no geometry on a hidden widget.
        if (widget) {
            widget->show();
        }
        entry.item->setGeometry(QRect(trailingX, area.top(), widths[i], area.height()));
        trailingX += widths[i];
    }

    // The rule down a panel's right edge separates it from its neighbour, so
    // the last of each group goes without.
    for (const Entry& entry : entries) {
        if (entry.panel) {
            entry.panel->setSeparatorVisible(entry.panel != lastLeading && entry.panel != lastTrailing);
        }
    }

    if (leaving != collapsed) {
        collapsed = leaving;
        page->setCollapsedPanels(collapsed);
    }
}
