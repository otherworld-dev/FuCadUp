// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026 FuCad contributors                                 *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#include "SnapGeometry.h"

#include <FCConfig.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <numbers>

#include <Precision.hxx>

#include <Base/Exception.h>

#include <Mod/Part/App/Geometry.h>

namespace Sketcher::SnapGeometry
{

int priority(SnapKind kind)
{
    switch (kind) {
        case SnapKind::Origin:
            return 8;
        case SnapKind::Vertex:
            return 7;
        case SnapKind::Intersection:
            return 6;
        case SnapKind::Midpoint:
            return 5;
        case SnapKind::Quadrant:
            return 4;
        case SnapKind::Axis:
            return 3;
        case SnapKind::OnCurve:
            return 2;
        case SnapKind::Grid:
            return 1;
        case SnapKind::None:
            break;
    }
    return 0;
}

std::optional<SnapCandidate> pickSnap(
    const std::vector<SnapCandidate>& candidates,
    const Base::Vector2d& cursor,
    double radius
)
{
    std::optional<SnapCandidate> best;
    double bestDistance = 0.0;

    for (const auto& candidate : candidates) {
        const double distance = (candidate.point - cursor).Length();
        if (distance > radius) {
            continue;
        }

        const bool outranks = !best || priority(candidate.kind) > priority(best->kind);
        const bool nearerOfSameRank = best && priority(candidate.kind) == priority(best->kind)
            && distance < bestDistance;

        if (outranks || nearerOfSameRank) {
            best = candidate;
            bestDistance = distance;
        }
    }

    return best;
}

namespace
{

Base::Vector2d toVector2d(const Base::Vector3d& v)
{
    return {v.x, v.y};
}

/// Start and end angles of an arc, counter-clockwise in the sketch plane, with end > start.
std::pair<double, double> ccwAngleRange(const Part::GeomArcOfCircle& arc)
{
    const Base::Vector3d center = arc.getCenter();
    const Base::Vector3d start = arc.getStartPoint(/*emulateCCWXY=*/true) - center;
    const Base::Vector3d end = arc.getEndPoint(/*emulateCCWXY=*/true) - center;

    const double startAngle = std::atan2(start.y, start.x);
    double endAngle = std::atan2(end.y, end.x);
    if (endAngle <= startAngle) {
        endAngle += 2.0 * std::numbers::pi;
    }
    return {startAngle, endAngle};
}

Base::Vector2d pointOnCircle(const Base::Vector3d& center, double radius, double angle)
{
    return {center.x + radius * std::cos(angle), center.y + radius * std::sin(angle)};
}

}  // namespace

std::optional<Base::Vector2d> midpoint(const Part::Geometry* geo)
{
    if (!geo) {
        return std::nullopt;
    }

    if (geo->is<Part::GeomLineSegment>()) {
        const auto* line = static_cast<const Part::GeomLineSegment*>(geo);
        return toVector2d((line->getStartPoint() + line->getEndPoint()) / 2.0);
    }

    if (geo->is<Part::GeomArcOfCircle>()) {
        const auto* arc = static_cast<const Part::GeomArcOfCircle*>(geo);
        const auto [startAngle, endAngle] = ccwAngleRange(*arc);
        return pointOnCircle(arc->getCenter(), arc->getRadius(), (startAngle + endAngle) / 2.0);
    }

    return std::nullopt;
}

std::vector<Base::Vector2d> quadrantPoints(const Part::Geometry* geo)
{
    if (!geo) {
        return {};
    }

    constexpr double halfPi = std::numbers::pi / 2.0;
    constexpr std::array<double, 4> quadrantAngles {0.0, halfPi, 2.0 * halfPi, 3.0 * halfPi};

    std::vector<Base::Vector2d> points;

    if (geo->is<Part::GeomCircle>()) {
        const auto* circle = static_cast<const Part::GeomCircle*>(geo);
        for (double angle : quadrantAngles) {
            points.push_back(pointOnCircle(circle->getCenter(), circle->getRadius(), angle));
        }
        return points;
    }

    if (geo->is<Part::GeomArcOfCircle>()) {
        const auto* arc = static_cast<const Part::GeomArcOfCircle*>(geo);
        const auto [startAngle, endAngle] = ccwAngleRange(*arc);
        constexpr double twoPi = 2.0 * std::numbers::pi;
        constexpr double tolerance = 1e-9;

        for (double angle : quadrantAngles) {
            // Bring the quadrant angle into [start, start + 2pi) and keep it if the arc reaches it.
            const double shifted = angle - twoPi * std::floor((angle - startAngle) / twoPi);
            if (shifted <= endAngle + tolerance) {
                points.push_back(pointOnCircle(arc->getCenter(), arc->getRadius(), angle));
            }
        }
        return points;
    }

    return points;
}

std::vector<Base::Vector2d> intersections(const Part::Geometry* a, const Part::Geometry* b)
{
    std::vector<Base::Vector2d> points;

    const auto* curveA = dynamic_cast<const Part::GeomCurve*>(a);
    const auto* curveB = dynamic_cast<const Part::GeomCurve*>(b);
    if (!curveA || !curveB || curveA == curveB) {
        return points;
    }

    std::vector<std::pair<Base::Vector3d, Base::Vector3d>> hits;
    try {
        if (!curveA->intersect(curveB, hits, Precision::Confusion())) {
            return points;
        }
    }
    catch (const Base::Exception&) {
        // Extrema can fail on degenerate pairs (e.g. overlapping lines); offer no snap then.
        return points;
    }

    // A shared endpoint is reported both as an endpoint match and as an extremum.
    constexpr double sameTolerance = 1e-7;
    for (const auto& [onA, onB] : hits) {
        const Base::Vector2d point = toVector2d(onA);
        const bool seen = std::any_of(points.begin(), points.end(), [&point](const Base::Vector2d& q) {
            return (q - point).Length() < sameTolerance;
        });
        if (!seen) {
            points.push_back(point);
        }
    }
    return points;
}

std::optional<Base::Vector2d> snapToGrid(
    const Base::Vector2d& point,
    double spacing,
    double tolerance,
    bool lockX,
    bool lockY
)
{
    if (spacing <= 0.0 || tolerance <= 0.0) {
        return std::nullopt;
    }

    // std::round rounds halves away from zero, as the grid drawing code does.
    auto nearestLine = [spacing](double value) {
        return std::round(value / spacing) * spacing;
    };

    Base::Vector2d snapped = point;
    bool snappedAny = false;

    if (!lockX) {
        const double line = nearestLine(point.x);
        if (std::abs(line - point.x) <= tolerance) {
            snapped.x = line;
            snappedAny = true;
        }
    }
    if (!lockY) {
        const double line = nearestLine(point.y);
        if (std::abs(line - point.y) <= tolerance) {
            snapped.y = line;
            snappedAny = true;
        }
    }

    if (!snappedAny) {
        return std::nullopt;
    }
    return snapped;
}

}  // namespace Sketcher::SnapGeometry
