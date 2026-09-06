// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Gui/ViewportGrid.h>

using Gui::ViewportGridLayout;

namespace
{
constexpr double baseSpacing = 10.0;
constexpr int subdivision = 10;
constexpr int viewportPixels = 1000;
constexpr int pixelThreshold = 15;
constexpr double tolerance = 1e-9;
}  // namespace

TEST(ViewportGridLayout, spacingHoldsTheBaseWhileLinesStayFarEnoughApart)
{
    // 200 mm across 1000 px puts 10 mm lines 50 px apart, well over the floor.
    EXPECT_NEAR(
        ViewportGridLayout::spacingFor(baseSpacing, subdivision, 200.0, viewportPixels, pixelThreshold),
        10.0,
        tolerance
    );
}

TEST(ViewportGridLayout, spacingGrowsByTheSubdivisionWhenZoomedOut)
{
    // 2000 mm across 1000 px would put 10 mm lines 5 px apart, under the floor.
    EXPECT_NEAR(
        ViewportGridLayout::spacingFor(baseSpacing, subdivision, 2000.0, viewportPixels, pixelThreshold),
        100.0,
        tolerance
    );
}

TEST(ViewportGridLayout, spacingShrinksByTheSubdivisionWhenZoomedIn)
{
    EXPECT_NEAR(
        ViewportGridLayout::spacingFor(baseSpacing, subdivision, 20.0, viewportPixels, pixelThreshold),
        1.0,
        tolerance
    );
}

TEST(ViewportGridLayout, spacingScalesByTenWhenTheSubdivisionCannotServeAsAFactor)
{
    EXPECT_NEAR(
        ViewportGridLayout::spacingFor(baseSpacing, 1, 2000.0, viewportPixels, pixelThreshold),
        100.0,
        tolerance
    );
}

TEST(ViewportGridLayout, spacingFallsBackToTheBaseForADegenerateView)
{
    EXPECT_NEAR(
        ViewportGridLayout::spacingFor(baseSpacing, subdivision, 0.0, viewportPixels, pixelThreshold),
        baseSpacing,
        tolerance
    );
    EXPECT_NEAR(
        ViewportGridLayout::spacingFor(baseSpacing, subdivision, 200.0, 0, pixelThreshold),
        baseSpacing,
        tolerance
    );
}

TEST(ViewportGridLayout, coveringCentredOnTheOriginIsSymmetric)
{
    const ViewportGridLayout layout = ViewportGridLayout::covering(10.0, subdivision, 0.0, 0.0, 100.0);

    EXPECT_EQ(layout.firstX, -5);
    EXPECT_EQ(layout.lastX, 5);
    EXPECT_EQ(layout.firstY, -5);
    EXPECT_EQ(layout.lastY, 5);
    EXPECT_EQ(layout.lineCount(), 22);
}

TEST(ViewportGridLayout, coveringRoundsOutwardsToWholeLines)
{
    const ViewportGridLayout layout = ViewportGridLayout::covering(10.0, subdivision, 123.0, -47.0, 100.0);

    EXPECT_EQ(layout.firstX, 7);    // 73 rounds out to 70
    EXPECT_EQ(layout.lastX, 18);    // 173 rounds out to 180
    EXPECT_EQ(layout.firstY, -10);  // -97 rounds out to -100
    EXPECT_EQ(layout.lastY, 1);     // 3 rounds out to 10
}

TEST(ViewportGridLayout, majorLinesFallOnMultiplesOfTheSubdivisionEitherSideOfTheOrigin)
{
    const ViewportGridLayout layout = ViewportGridLayout::covering(10.0, subdivision, 0.0, 0.0, 100.0);

    EXPECT_TRUE(layout.isMajor(0));
    EXPECT_TRUE(layout.isMajor(10));
    EXPECT_TRUE(layout.isMajor(-20));
    EXPECT_FALSE(layout.isMajor(5));
    EXPECT_FALSE(layout.isMajor(-3));
}

TEST(ViewportGridLayout, everyLineIsMajorWhenTheSubdivisionIsOne)
{
    const ViewportGridLayout layout = ViewportGridLayout::covering(10.0, 1, 0.0, 0.0, 100.0);

    EXPECT_TRUE(layout.isMajor(3));
    EXPECT_TRUE(layout.isMajor(-7));
}

TEST(ViewportGridLayout, positionIsTheIndexTimesTheSpacing)
{
    const ViewportGridLayout layout = ViewportGridLayout::covering(2.5, subdivision, 0.0, 0.0, 10.0);

    EXPECT_NEAR(layout.position(-2), -5.0, tolerance);
    EXPECT_NEAR(layout.position(3), 7.5, tolerance);
}
